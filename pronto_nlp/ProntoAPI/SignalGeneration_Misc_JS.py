import re

from SelectRelation_ExtraMetadata_JS import GetExtraMetadataColumns, GetExtraMetadataColumnValues


# "Ticker,Date" -> [ #allSentences, #AllDLPos, #AllDLNeg, #AllDLPosDiscounted, #AllDLNegDiscounted,
#                  { EventType => [#All, #EPos, #ENeg] } ]
FullSignalData = {}

def GetAllDocIDsForSignals():
  return [GetDocIDFromDateTickerDocID(dateTickerDocID) for dateTickerDocID in FullSignalData.keys()]

def GetDocIDFromDateTickerDocID(dateTickerDocID):
  iPosTicker = dateTickerDocID.find(',') + 1
  iPosDocID = dateTickerDocID.find(',', iPosTicker) + 1
  return dateTickerDocID[iPosDocID:]


def GenerateSet(L): return set(L)

GrowthEventsPos = GenerateSet([
  'Revenue - Positive', 'Technology - Positive', 'ProductLaunch - Positive', 'Growth - Positive',
  'Opportunity - Positive', 'Facilities - Positive', 'Excited - Positive', 'Tailwinds - Positive',
  'RecordResults - Positive', 'DealContract - Positive', 'MarketShare - Positive',
  'Outlook - Positive', 'SupplyChain - Positive', 'MediaContent - Positive', 'Acquisitions - Positive',
  'CustomerSpending - Positive', 'CustomerFeedback - Positive', 'StrategicAlliance - Positive',
  'ResearchDevelopment - Positive' ])

GrowthEventsNeg = GenerateSet([
  'Costs - Negative', 'Logistics - Negative', 'CashFlow - Negative',
  'CovidImpact - Negative', 'Inventory - Negative', 'Diversification - Negative' ])

ValueEventsPos = GenerateSet([
  'Margin - Positive', 'Costs - Positive', 'MetricsChange - Positive', 'Dividend - Positive',
  'BalanceSheet - Positive', 'CreditRating - Positive', 'Performance - Positive',
  'ProfitsEarnings - Positive', 'CopeWithInflation - Positive', 'ShareholderReturn - Positive',
  'Tax - Positive', 'Synergy - Positive', 'Backlog - Positive' ])

ValueEventsNeg = GenerateSet([
  'Revenue - Negative', 'Headwinds - Negative', 'MetricsChange - Negative', 'ProfitsEarnings - Negative',
  'Demand - Negative', 'Growth - Negative', 'Inflation - Negative', 'RawMaterial - Negative',
  'SupplyChain - Negative', 'Outlook - Negative', 'Workforce - Negative', 'RecordResults - Negative' ])


def ContainsAnyWColumn(WColumnsSet, columnsSet):
  return any(x in columnsSet for x in WColumnsSet)

def CalcWeightedSum(sum, WColumnsSet, ETInfoCopy):
  for sEventKey, iCount in ETInfoCopy.items():
    if sEventKey in WColumnsSet:
      sum += 2 * iCount
  return sum


def CalcWeightedColumns(EPos, ENeg, WColumnsSetPos, WColumnsSetNeg, ETInfoCopy):
  WEPos = CalcWeightedSum(EPos, WColumnsSetPos, ETInfoCopy)
  WENeg = CalcWeightedSum(ENeg, WColumnsSetNeg, ETInfoCopy)
  WScore = (WEPos - WENeg) / (WEPos + WENeg + 1)
  return [WEPos, WENeg, WScore]


def GenerateSignalCSV_ProcessingAPI():
  SignalData = CopyFullSignalData(FullSignalData)
  #MergeMatchesIntoSignalData(MatchesData, SignalData);

  sortedSignalData = []
  eventKeysSet = set()
  for dateTickerDocID, D in SignalData.items():
    sortedSignalData.append([dateTickerDocID, *D[0:8]])
    eventKeysSet.update(D[7].keys())  # ETInfoCopy = D[7]
  sortedEventKeys = sorted(eventKeysSet)
  sortedSignalData.sort()

  fIsTranscript = True
  fIsMacro = False
  extraMetadataColumnsUpperCase = [C.upper() for C in GetExtraMetadataColumns()]
  iCorpusIndex = extraMetadataColumnsUpperCase.index('CORPUS') if 'CORPUS' in extraMetadataColumnsUpperCase else -1
  if iCorpusIndex >= 0:
    for D in sortedSignalData:
      dateTickerDocID = D[0]
      metadataValues = GetExtraMetadataColumnValues(dateTickerDocID)
      if len(metadataValues) > iCorpusIndex and metadataValues[iCorpusIndex]:
        sCorpus = metadataValues[iCorpusIndex].lower()
        fIsTranscript = (sCorpus == 'transcripts')
        fIsMacro = (sCorpus == 'federalreserveboard' or sCorpus == 'bankofengland' or sCorpus == 'europeancentralbank')
        break
  fUseGrowth = fIsTranscript and (ContainsAnyWColumn(GrowthEventsPos, eventKeysSet) or ContainsAnyWColumn(GrowthEventsNeg, eventKeysSet))
  fUseValue = fIsTranscript and (ContainsAnyWColumn(ValueEventsPos, eventKeysSet) or ContainsAnyWColumn(ValueEventsNeg, eventKeysSet))

  columns = ((["DocDate,DocID"] if fIsMacro else ["DocDate,Ticker,DocID"])
             + GetExtraMetadataColumns()
             + (["Sentences", "LLMDove", "LLMHawk", "AllLLMDove", "AllLLMHawk", "EventDove", "EventHawk"] if fIsMacro else
                ["Sentences", "DLPos", "DLNeg", "AllDLPos", "AllDLNeg", "EventPos", "EventNeg"])
             + (["Combined Sentiment Score", "LLM Sentiment Score", "Events Sentiment Score"] if fIsMacro else
                ["Combined Sentiment Score", "DL Sentiment Score", "Events Sentiment Score"])
             + (["GrowthWeightedPos", "GrowthWeightedNeg", "GrowthWeighted Sentiment Score"] if fUseGrowth else [])
             + (["ValueWeightedPos", "ValueWeightedNeg", "ValueWeighted Sentiment Score"] if fUseValue else [])
             + sortedEventKeys)
  column2Index = {c:i for i,c in enumerate(columns)}
  if fIsMacro:
    for i in range(len(columns)):
      columns[i] = re.sub(r' - Positive$', ' - Dovish', columns[i])
      columns[i] = re.sub(r' - Negative$', ' - Hawkish', columns[i])

  rows = []
  for [dateTickerDocID, allSentences, AllDLPos, AllDLNeg, AllDLPosDiscounted, AllDLNegDiscounted, EPos, ENeg, ETInfoCopy] in sortedSignalData:
    AllDLPosDiscounted += EPos
    AllDLNegDiscounted += ENeg
    dCombinedSentimentScore = (AllDLPosDiscounted - AllDLNegDiscounted) / (AllDLPosDiscounted + AllDLNegDiscounted + 1)
    dDLSentimentScore = (AllDLPos - AllDLNeg) / (AllDLPos + AllDLNeg + 1)
    dEventsSentimentScore = (EPos - ENeg) / (EPos + ENeg + 1)
    sFirstValues = re.sub(r',[^,]*,', ',', dateTickerDocID) if fIsMacro else dateTickerDocID
    rowData = ([sFirstValues]
               + GetExtraMetadataColumnValues(dateTickerDocID)
               + [allSentences, AllDLPosDiscounted-EPos, AllDLNegDiscounted-ENeg, AllDLPos, AllDLNeg, EPos, ENeg]
               + [dCombinedSentimentScore, dDLSentimentScore, dEventsSentimentScore]
               + (CalcWeightedColumns(EPos, ENeg, GrowthEventsPos, GrowthEventsNeg, ETInfoCopy) if fUseGrowth else [])
               + (CalcWeightedColumns(EPos, ENeg, ValueEventsPos, ValueEventsNeg, ETInfoCopy) if fUseValue else [])
                  )
    for [sEventKey, iCount] in ETInfoCopy.items():
      iColumn = column2Index[sEventKey]
      while len(rowData) <= iColumn: rowData.append("")
      rowData[iColumn] = iCount

    rows.append(','.join(str(s) for s in rowData))

  return ','.join(columns) + '\n' + '\n'.join(rows)


def CopyFullSignalData(fullSignalData):
  signalData = {}
  for [dateTickerDocID, [allSentences, AllDLPos, AllDLNeg, DLPosDiscounted, DLNegDiscounted, ETInfo]] in fullSignalData.items():
    if not allSentences: continue
    SumEPos = 0
    SumENeg = 0
    ETInfoCopy = {}
    for [ET, [EAll, EPos, ENeg]] in ETInfo.items():
      ENeu = EAll - (EPos + ENeg)
      if EPos > 0: ETInfoCopy[ET + " - Positive"] = EPos;  SumEPos += EPos
      if ENeg > 0: ETInfoCopy[ET + " - Negative"] = ENeg;  SumENeg += ENeg
      if ENeu > 0: ETInfoCopy[ET + " - Neutral"]  = ENeu;
    signalData[dateTickerDocID] = [allSentences, AllDLPos, AllDLNeg, DLPosDiscounted, DLNegDiscounted, SumEPos, SumENeg, ETInfoCopy]
  return signalData


def AddNewFullSignalData(dataList):
  for [dateTickerDocID, allSentences, DLPos, DLNeg, DLPosDiscounted, DLNegDiscounted, ETInfo] in dataList:
    existingData = FullSignalData.get(dateTickerDocID, None)
    if existingData is None:
      FullSignalData[dateTickerDocID] = [allSentences, DLPos, DLNeg, DLPosDiscounted, DLNegDiscounted, ETInfo]
    else:
      existingData[0] += allSentences
      existingData[1] += DLPos
      existingData[2] += DLNeg
      existingData[3] += DLPosDiscounted
      existingData[4] += DLNegDiscounted
      for [ET, [EAll, EPos, ENeg]] in ETInfo.items():
        existingETData = existingData[4].get(ET, None)
        if existingETData is None:
          existingData[4][ET] = [EAll, EPos, ENeg]
        else:
          existingETData[0] += EAll
          existingETData[1] += EPos
          existingETData[2] += ENeg
