## Introduction

This project is mainly a text-to-sql system, which provides the construction company to ask the LLM about the information of some constructions via natural language.

Ex: 大樓工程中的假設工程中的子工程，基地整地需要的檢查表有哪些？
Ans: 基地整地需要開挖作業安全檢查表, 露天開挖作業安全檢查表, 一般安衛檢查表

![Demo video](./demo.mov)

## System Design

Below is the overall design of the system.
![System design](./system-design.png)

- Step 1: Extract keywords from users' input using LLM
- Step 2: Replace keywords from users' input with actual keywords
- Step 3: Send the modified input to LLM to write query & execute
- Step 4: Send the result to another LLM to summarize

Example Process:

Step 1, 2:

User Input: 大樓工中的甲設工程中的子工程，積地整地需要的檢查表有哪些？
Extracted keywords: ['大樓工', '甲設工程', '積地整地']
Find possible real keywords: [('大樓工', '大樓工程'), ('甲設工程', '假設工程'), ('積地整地', '基地整地')]
Replace User Input with possible real keywords: 大樓工程中的假設工程中的子工程，基地整地需要的檢查表有哪些？

Step 3:

Input the user input to the chain to get the result. The input will first execute in a chain if there's no error, otherwise we will apply agent to debug the error which may cause multiple api calls. In order to deal with the cost, we apply gpt-4 to the chain and gpt-3.5 to the agent.

Step 4:

Input the query result and answer the user.
Ans: 基地整地需要開挖作業安全檢查表, 露天開挖作業安全檢查表, 一般安衛檢查表


## Database Design

Since the company stores the data currently in excel, we need to design the database for them.
For the overall database design, please refer to ![Database Design](./v1.0/database_introduction.md)

## Further Works

- Transfer all the company's data to database
- Evaluation on loading keywords mechanism mentioned at System Design
    - When to load?
    - How often should we reload the keyword buffer?

- Different ways to store keywords
    - Embedding
    - actual words