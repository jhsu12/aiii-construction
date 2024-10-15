CREATE TABLE `Construction` (
  `ID` int PRIMARY KEY,
  `Name` varchar(100)
);

CREATE TABLE `SubConstruction` (
  `ID` int PRIMARY KEY,
  `Name` varchar(100)
);

CREATE TABLE `SubConstructionDetails` (
  `ID` int PRIMARY KEY,
  `Name` varchar(100)
);

CREATE TABLE `CheckingDocs` (
  `ID` int PRIMARY KEY,
  `Name` varchar(100),
  `Link` varchar(2048)
);

CREATE TABLE `CheckingStandard` (
  `ID` int PRIMARY KEY,
  `Name` varchar(100),
  `TypeID` int
);

CREATE TABLE `Type` (
  `ID` int PRIMARY KEY,
  `Name` varchar(100),
  `Symbol` varchar(1)
);

CREATE TABLE `ConstructionSubConstructionPair` (
  `ConstructionID` int,
  `SubConstructionID` int,
  `Sequence` int,
  PRIMARY KEY (`ConstructionID`, `SubConstructionID`)
);

CREATE TABLE `SubConstructionSubConstructionDetailsPair` (
  `SubConstructionID` int,
  `SubConstructionDetailsID` int,
  `Sequence` int,
  PRIMARY KEY (`SubConstructionID`, `SubConstructionDetailsID`)
);

CREATE TABLE `SubConstructionDetailCheckingDoc` (
  `SubConstructionDetailID` int,
  `CheckingDocID` int,
  PRIMARY KEY (`SubConstructionDetailID`, `CheckingDocID`)
);

CREATE TABLE `SubConstructionDetailCheckingStandard` (
  `SubConstructionDetailID` int,
  `CheckingStandardID` int,
  PRIMARY KEY (`SubConstructionDetailID`, `CheckingStandardID`)
);

ALTER TABLE `CheckingStandard` ADD FOREIGN KEY (`TypeID`) REFERENCES `Type` (`ID`);

ALTER TABLE `ConstructionSubConstructionPair` ADD FOREIGN KEY (`ConstructionID`) REFERENCES `Construction` (`ID`);

ALTER TABLE `ConstructionSubConstructionPair` ADD FOREIGN KEY (`SubConstructionID`) REFERENCES `SubConstruction` (`ID`);

ALTER TABLE `SubConstructionSubConstructionDetailsPair` ADD FOREIGN KEY (`SubConstructionID`) REFERENCES `SubConstruction` (`ID`);

ALTER TABLE `SubConstructionSubConstructionDetailsPair` ADD FOREIGN KEY (`SubConstructionDetailsID`) REFERENCES `SubConstructionDetails` (`ID`);

ALTER TABLE `SubConstructionDetailCheckingDoc` ADD FOREIGN KEY (`SubConstructionDetailID`) REFERENCES `SubConstructionDetails` (`ID`);

ALTER TABLE `SubConstructionDetailCheckingDoc` ADD FOREIGN KEY (`CheckingDocID`) REFERENCES `CheckingDocs` (`ID`);

ALTER TABLE `SubConstructionDetailCheckingStandard` ADD FOREIGN KEY (`SubConstructionDetailID`) REFERENCES `SubConstructionDetails` (`ID`);

ALTER TABLE `SubConstructionDetailCheckingStandard` ADD FOREIGN KEY (`CheckingStandardID`) REFERENCES `CheckingStandard` (`ID`);
