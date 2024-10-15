import ast
from typing import Dict, List, Tuple

import redis
from configs.config import Config
from langchain.chains import create_sql_query_chain
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.callbacks import get_openai_callback
from langchain_community.utilities import SQLDatabase
from langchain_community.vectorstores import FAISS
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_core.output_parsers import SimpleJsonOutputParser, StrOutputParser
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotPromptTemplate,
    PromptTemplate,
)
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langsmith import Client
from mysql import connector

rd = redis.Redis(host='localhost', port=6379, db=0)

class KeywordExtractor:
    def __init__(self, db):
        self.db = db

    def get_keywords(self, tables: List) -> List[str]:
        # check if cache hit
        cache = rd.get('keywords')
        if cache:
            print("Cache hit")
            # convert string representation of list to list
            kw_list = ast.literal_eval(cache.decode('utf-8'))
            # print(kw_list)
            return kw_list
        else:
            print("Cache miss")
            kw = []
            for t in tables:
                result = self.db.run(f"SELECT * FROM prod.{t};")
                result_list = ast.literal_eval(result)
                for k in result_list:
                    kw.append(k[1])
            rd.set("keywords", f"{kw}")
            # set expire time in second
            rd.expire("keywords", 600)
        return kw


class StringModifier:
    def __init__(self, example: str, keywords_list: List[str]):
        self.keywords_list = keywords_list
        self.example = example
        self.keyword_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "請你將使用者輸入的字串提取關鍵字，請不要更改句子中的字，以下是範例 {example}, 請將關鍵字以list形式輸出，只要輸出list就好",
                ),
                ("human", "{input}"),
            ]
        ).partial(example=example)

    def modify_string(self, text: str, llm: AzureChatOpenAI) -> str:
        kw_chain = self.keyword_prompt | llm
        label_words = ast.literal_eval(kw_chain.invoke({"input": text}).content)
        modified_string = self.replace_highest_frequency_text(label_words, text)
        return modified_string

    @staticmethod
    def calculate_word_frequency(user_keyword: str, text: str) -> float:
        matched_chars = sum(1 for char in user_keyword if char in text)
        return matched_chars / len(text)

    def replace_highest_frequency_text(
        self, label_words: List[str], original_string: str
    ) -> str:
        highest_frequency_texts = {}

        for label_word in label_words:
            max_frequency = 0
            best_text = ""
            for kw in self.keywords_list:
                frequency = self.calculate_word_frequency(label_word, kw)
                if frequency > max_frequency:
                    max_frequency = frequency
                    best_text = kw
            highest_frequency_texts[label_word] = (best_text, max_frequency)
        print(f"Frequency \n {highest_frequency_texts}")
        for label_word in label_words:
            original_string = original_string.replace(
                label_word, highest_frequency_texts[label_word][0]
            )

        return original_string


class SQLQueryAgent:
    def __init__(
        self, llm: AzureChatOpenAI, db: SQLDatabase, embeddings: AzureOpenAIEmbeddings
    ):
        # self.agent_executor = create_sql_agent(
        #     llm, db, agent_type="openai-tools", verbose=True
        # )
        self.db = db
        self.llm = llm
        self.embeddings = embeddings

    def write_query(self, question: str) -> str:
        examples = [
            {
                "input": "大樓工程中的假設工程需要做的工程為何？",
                "query": """SELECT `scd`.`Name`
                FROM `Construction` AS `c`
                JOIN `ConstructionSubConstructionPair` AS `cscp` ON `c`.`ID` = `cscp`.`ConstructionID`
                JOIN `SubConstruction` AS `sc` ON `cscp`.`SubConstructionID` = `sc`.`ID`
                JOIN `SubConstructionSubConstructionDetailsPair` AS `scsdp` ON `sc`.`ID` = `scsdp`.`SubConstructionID`
                JOIN `SubConstructionDetails` AS `scd` ON `scsdp`.`SubConstructionDetailsID` = `scd`.`ID`
                WHERE `c`.`Name` = '大樓工程' AND `sc`.`Name` = '假設工程'""",
            },
            {
                "input": "大樓工程中的假設工程中的子工程，臨時用電需要的檢查表有哪些？",
                "query": """ SELECT `cd`.`Name` AS `CheckingDocName`
                        FROM `Construction` AS `c`
                        JOIN `ConstructionSubConstructionPair` AS `cscp` ON `c`.`ID` = `cscp`.`ConstructionID`
                        JOIN `SubConstruction` AS `sc` ON `cscp`.`SubConstructionID` = `sc`.`ID`
                        JOIN `SubConstructionSubConstructionDetailsPair` AS `scsdp` ON `sc`.`ID` = `scsdp`.`SubConstructionID`
                        JOIN `SubConstructionDetails` AS `scd` ON `scsdp`.`SubConstructionDetailsID` = `scd`.`ID`
                        JOIN `SubConstructionDetailCheckingDoc` AS `scdcd` ON `scd`.`ID` = `scdcd`.`SubConstructionDetailID`
                        JOIN `CheckingDocs` AS `cd` ON `scdcd`.`CheckingDocID` = `cd`.`ID`
                        WHERE `c`.`Name` = '大樓工程' AND `sc`.`Name` = '假設工程' AND `scd`.`Name` = '臨時用電'""",
            },
            {
                "input": "大樓工程中的假設工程中的子工程，安全走廊工程需要的檢查表有哪些？",
                "query": """ SELECT `cd`.`Name` AS `CheckingDocName`
                        FROM `Construction` AS `c`
                        JOIN `ConstructionSubConstructionPair` AS `cscp` ON `c`.`ID` = `cscp`.`ConstructionID`
                        JOIN `SubConstruction` AS `sc` ON `cscp`.`SubConstructionID` = `sc`.`ID`
                        JOIN `SubConstructionSubConstructionDetailsPair` AS `scsdp` ON `sc`.`ID` = `scsdp`.`SubConstructionID`
                        JOIN `SubConstructionDetails` AS `scd` ON `scsdp`.`SubConstructionDetailsID` = `scd`.`ID`
                        JOIN `SubConstructionDetailCheckingDoc` AS `scdcd` ON `scd`.`ID` = `scdcd`.`SubConstructionDetailID`
                        JOIN `CheckingDocs` AS `cd` ON `scdcd`.`CheckingDocID` = `cd`.`ID`
                        WHERE `c`.`Name` = '大樓工程' AND `sc`.`Name` = '假設工程' AND `scd`.`Name` = '安全走廊工程'""",
            },
            {
                "input": "大樓工程中的假設工程中的子工程，'安全圍籬工程'需要做的檢查有哪些？",
                "query": " SELECT `Name` FROM `CheckingStandard` WHERE `ID` IN (SELECT `CheckingStandardID` FROM `SubConstructionDetailCheckingStandard` WHERE `SubConstructionDetailID` = (SELECT `ID` FROM `SubConstructionDetails` WHERE `Name` = '安全圍籬工程'))",
            },
            {
                "input": "大樓工程中的假設工程中的子工程，'安全圍籬工程'需要的類別'一般其他類檢查'有哪些？",
                "query": """ SELECT `cs`.`Name`
                FROM `SubConstructionDetails` AS `scd`
                JOIN `SubConstructionDetailCheckingStandard` AS `scdcs` ON `scd`.`ID` = `scdcs`.`SubConstructionDetailID`
                JOIN `CheckingStandard` AS `cs` ON `scdcs`.`CheckingStandardID` = `cs`.`ID`
                JOIN `CheckingStandardType` AS `cst` on `cs`.`TypeID` = `cst`.`ID`
                WHERE `scd`.`Name` = '安全圍籬工程' AND `cst`.`Name` = '一般其他類'""",
            },
            {
                "input": "大樓工程中的假設工程中的子工程，需要'臨時照明 (日光燈)'檢查標準的工程有哪些？",
                "query": """ SELECT `scd`.`Name`
                    FROM `Construction` AS `c`
                    JOIN `ConstructionSubConstructionPair` AS `cscp` ON `c`.`ID` = `cscp`.`ConstructionID`
                    JOIN `SubConstruction` AS `sc` ON `cscp`.`SubConstructionID` = `sc`.`ID`
                    JOIN `SubConstructionSubConstructionDetailsPair` AS `scsdp` ON `sc`.`ID` = `scsdp`.`SubConstructionID`
                    JOIN `SubConstructionDetails` AS `scd` ON `scsdp`.`SubConstructionDetailsID` = `scd`.`ID`
                    JOIN `SubConstructionDetailCheckingStandard` AS `scdcs` ON `scd`.`ID` = `scdcs`.`SubConstructionDetailID`
                    JOIN `CheckingStandard` AS `cs` ON `scdcs`.`CheckingStandardID` = `cs`.`ID`
                    WHERE `c`.`Name` = '大樓工程' AND `sc`.`Name` = '假設工程' AND `cs`.`Name` = '臨時照明 (日光燈)'""",
            },
            {
                "input": "大樓工程中的假設工程中的子工程順序為何？",
                "query": """ SELECT `scd`.`Name`, `scsdp`.`Sequence`
                    FROM `SubConstructionDetails` AS `scd`
                    JOIN `SubConstructionSubConstructionDetailsPair` AS `scsdp` ON `scd`.`ID` = `scsdp`.`SubConstructionDetailsID`
                    JOIN `SubConstruction` AS `sc` ON `scsdp`.`SubConstructionID` = `sc`.`ID`
                    JOIN `ConstructionSubConstructionPair` AS `cscp` ON `sc`.`ID` = `cscp`.`SubConstructionID`
                    JOIN `Construction` AS `c` ON `cscp`.`ConstructionID` = `c`.`ID`
                    WHERE `c`.`Name` = '大樓工程' AND `sc`.`Name` = '假設工程'
                    ORDER BY `scsdp`.`Sequence`""",
            },
            {
                "input": "大樓工程中的假設工程中的子工程，抽排風下一個工程為何？",
                "query": """SELECT `scd`.`Name` 
                    FROM `SubConstructionDetails` AS `scd`
                    JOIN `SubConstructionSubConstructionDetailsPair` AS `scdp` ON `scd`.`ID` = `scdp`.`SubConstructionDetailsID`
                    WHERE `scdp`.`SubConstructionID` = (SELECT `ID` FROM `SubConstruction` WHERE `Name` = '假設工程')
                    AND `scdp`.`Sequence` = (
                        SELECT `Sequence` + 1 
                        FROM `SubConstructionSubConstructionDetailsPair` 
                        WHERE `SubConstructionID` = (SELECT `ID` FROM `SubConstruction` WHERE `Name` = '假設工程') 
                        AND `SubConstructionDetailsID` = (SELECT `ID` FROM `SubConstructionDetails` WHERE `Name` = '抽排風')
                    )
                    LIMIT 1;""",
            },
            {
                "input": "在'大樓工程'中的'假設工程'，哪些工程需要'臨時用電 (水銀燈)'檢查標準?",
                "query": """SELECT `scd`.`Name` 
                    FROM `Construction` AS `c` 
                    JOIN `ConstructionSubConstructionPair` AS `cscp` ON `c`.`ID` = `cscp`.`ConstructionID` 
                    JOIN `SubConstruction` AS `sc` ON `cscp`.`SubConstructionID` = `sc`.`ID` 
                    JOIN `SubConstructionSubConstructionDetailsPair` AS `scsdp` ON `sc`.`ID` = `scsdp`.`SubConstructionID` 
                    JOIN `SubConstructionDetails` AS `scd` ON `scsdp`.`SubConstructionDetailsID` = `scd`.`ID` 
                    JOIN `SubConstructionDetailCheckingStandard` AS `scdcs` ON `scd`.`ID` = `scdcs`.`SubConstructionDetailID` 
                    JOIN `CheckingStandard` AS `cs` ON `scdcs`.`CheckingStandardID` = `cs`.`ID` WHERE `c`.`Name` = '大樓工程' AND `sc`.`Name` = '假設工程' AND `cs`.`Name` = '臨時用電 (水銀燈)'""",
            },
            {
                "input": "在'大樓工程'中的'假設工程'，哪些工程需要類別為'一般其他類'的檢查標準?",
                "query": """SELECT distinct(`scd`.`Name`) AS `SubConstructionDetailName` 
                    FROM `Construction` AS `c` 
                    JOIN `ConstructionSubConstructionPair` AS `cscp` ON `c`.`ID` = `cscp`.`ConstructionID` 
                    JOIN `SubConstruction` AS `sc` ON `cscp`.`SubConstructionID` = `sc`.`ID` 
                    JOIN `SubConstructionSubConstructionDetailsPair` AS `scsdp` ON `sc`.`ID` = `scsdp`.`SubConstructionID` 
                    JOIN `SubConstructionDetails` AS `scd` ON `scsdp`.`SubConstructionDetailsID` = `scd`.`ID` 
                    JOIN `SubConstructionDetailCheckingStandard` AS `scdcs` ON `scd`.`ID` = `scdcs`.`SubConstructionDetailID` 
                    JOIN `CheckingStandard` AS `cs` ON `scdcs`.`CheckingStandardID` = `cs`.`ID` 
                    JOIN `CheckingStandardType` AS `cst` ON `cs`.`TypeID` = `cst`.`ID` WHERE `c`.`Name` = '大樓工程' AND `sc`.`Name` = '假設工程' AND `cst`.`Name` = '一般其他類'""",
            },
        ]
        system = """You are a {dialect} expert. Given an input question, create a syntactically correct {dialect} query to run.
                Unless the user specifies in the question a specific number of examples to obtain, query for at most {top_k} results using the LIMIT clause as per {dialect}. You can order the results to return the most informative data in the database.
                Never query for all columns from a table. You must query only the columns that are needed to answer the question. 
                Pay attention to use only the column names you can see in the tables below. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
                Pay attention to use date('now') function to get the current date, if the question involves "today". Also, if the user request to query with a specific string match, please make sure in the database, there's value similar to the string when the user has a typo. Lastly, you are only
                able to use "SELECT" keyword. You can't modify the database!

                Only use the following tables:
                {table_info}

                Write an initial draft of the query. Then double check the {dialect} query for common mistakes, including:
                - Using NOT IN with NULL values
                - Using UNION when UNION ALL should have been used
                - Using BETWEEN for exclusive ranges
                - Data type mismatch in predicates
                - Properly quoting identifiers
                - Using the correct number of arguments for functions
                - Casting to the correct data type
                - Using the proper columns for joins

                Use format:

                Please output the mysql query only, and don't add "'''sql" in the begining, just output a sql query string only!

                Below are a number of examples of questions and their corresponding SQL queries.
                """
        example_selector = SemanticSimilarityExampleSelector.from_examples(
            examples,
            self.embeddings,
            FAISS,
            k=3,
            input_keys=["input"],
        )
        example_prompt = PromptTemplate.from_template(
            "User input: {input}\nSQL query: {query}"
        )
        prompt = FewShotPromptTemplate(
            example_selector=example_selector,
            example_prompt=example_prompt,
            prefix=system,
            suffix="User input: {input}\nSQL query: ",
            input_variables=["input", "top_k", "table_info"],
        )

        write_query_few_shot = create_sql_query_chain(self.llm, self.db, prompt, k=100)
        return write_query_few_shot.invoke({"question": question})

    def run_query(self, query: str, question: str) -> str:
        try:
            result = self.db.run(query)
        except Exception as e:
            print(f"error when running query: {e}")
            error_message = f"Please fix the error of sql query. Question: {question} Error: {str(e)} Query: {query}"
            llm3 = AzureChatOpenAI(
                azure_endpoint=Config.OPENAI_API_BASE_URL,
                openai_api_version="2024-02-01",
                azure_deployment='gpt-3.5-turbo',
                openai_api_key=Config.OPENAI_API_KEY,
                validate_base_url=False,
                temperature=Config.TEMPERATURE,
            )
            agent_executor = create_sql_agent(llm3, self.db, agent_type="openai-tools", verbose=True)
            result = agent_executor.invoke(error_message)["output"]
        return result

    def get_result(self, question: str) -> str:
        # write query
        query = self.write_query(question)

        # run query
        result = self.run_query(query, question)

        return result


llm4 = AzureChatOpenAI(
    azure_endpoint=Config.OPENAI_API_BASE_URL,
    openai_api_version="2024-02-01",
    azure_deployment=Config.MODEL_NAME,
    openai_api_key=Config.OPENAI_API_KEY,
    temperature=Config.TEMPERATURE,
)

embeddings = AzureOpenAIEmbeddings(
    api_key=Config.AZURE_OPENAI_KEY,
    azure_deployment=Config.AZURE_DEPLOYMENT,
    openai_api_version="2023-05-15",
    azure_endpoint=Config.AZURE_OPENAI_BASE_URL,
)







def get_construct_info(question):
    

    #global keyword_extractor
    global llm4, embeddings
    # Keyword extraction and replacement logic
    # Prevent getting keywords all the time when the user input
    try:
        db = SQLDatabase.from_uri(Config.MYSQL_URI)
        print("Successfully connected to the database")
    except:
        print("Error when connecting to db")
    #How to cache keywords

    # if keyword_extractor is None:
    keyword_extractor = KeywordExtractor(db)
    print("Initialize keyword_extractor")
    tables = [
        "SubConstructionDetails",
        "SubConstruction",
        "Construction",
        "CheckingStandard",
        "CheckingDocs",
        "CheckingStandardType",
    ]
    keywords_list = keyword_extractor.get_keywords(tables)
    print("Get keywords")
    # modified string
    example = """
                Example1:
                    使用者:"大樓工程中的假設工程中的子工程，基地整地需要的一般其他類檢查標準有哪些？"
                    關鍵字: ['大樓工程', '假設工程', '基地整地', '一般其他類']
                Example2:
                    使用者:"大樓工程中的假設工程中的子工程，施工便道工程需要的墜落防止檢查標準有哪些？"
                    關鍵字: ['大樓工程', '假設工程', '施工便道工程', '墜落防止']
                Example3:
                    使用者:"大樓工程中的假設工程，需要做的子工程順序？"
                    關鍵字: ['大樓工程', '假設工程', '施工便道工程', '墜落防止']
                Example4:
                    使用者:"大樓工程中的假設工程中的子工程，支撐架需要的檢查表有哪些？"
                    關鍵字: ['大樓工程', '假設工程', '支撐架']
                Example5:
                    使用者:"在大樓工程中的假設工程，哪些工程需要類別為環境保護的檢查標準?"
                    關鍵字: ['大樓工程', '假設工程', '環境保護']
                """
    string_modifier = StringModifier(example, keywords_list)
    modified_string = string_modifier.modify_string(question, llm4)
    print("Modify string")
    # write&run query
    sqlAgent = SQLQueryAgent(llm4, db, embeddings)
    print("Get the result")
    result = sqlAgent.get_result(modified_string)
    
    # explaination
    answer_prompt = PromptTemplate.from_template(
        """Given the following user question, and SQL result, answer the user question in Traditional Chinese.
            If the result is empty, it means that there's no data according to the question. Please answer NO with relevent question.
            For example, question "How many classes does Jason need to go on Monday?", if the reslt is empty, you shoiuld answer like 
            "Jason has no class on Monday."

    Question: {question}
    SQL Result: {result}
    Answer: """
    )

    chain = answer_prompt | llm4 | StrOutputParser()
    
    json_data = {"response": "", "token_usage": {}}
    with get_openai_callback() as cb:
        
        # explaination = chain.invoke({"question": modified_string, "result": result}, stream=True)
        for chunk in chain.stream({"question": modified_string, "result": result}):
            json_data["response"] += chunk
            # not able to streamline while tracking token usage https://python.langchain.com/docs/how_to/llm_token_usage_tracking/
            # But you can see the token usage in Langsmith
            # json_data["token_usage"] = {
            #     "Total Tokens": cb.total_tokens,
            #     "Prompt Tokens": cb.prompt_tokens,
            #     "Completion Tokens": cb.completion_tokens,
            #     "Total Cost (USD)": cb.total_cost,
            # }
            yield json_data
            
            
    # return json_data
