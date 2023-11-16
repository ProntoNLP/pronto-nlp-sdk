import re
import json
import sys

from .SelectRelation_ExtraMetadata_JS import GetExtraMetadataColumns, GetExtraMetadataColumnValues, MakeCSVField


reEvent = re.compile(r'<EVENT([^>]*)>(.*?)</EVENT>')
reEventProp = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)="([^"]+)"')
reSlot = re.compile(r'<SLOT([^>]*)>(.*?)</SLOT>')

def GetMetadataInfo(sXML):
  M = re.search(r'^<METADATA value="(?:([A-Z]*\d+)(?:_\d+)*,\s*)?(\d\d\d\d-\d\d-\d\d)\b[^,]*(?:,\s*([^"]*?)\s*)??(?:,\s*([+\-]?\d+(?:\.\d+)?)\s*)?(?:,\s*(#[a-zA-Z_0-9]+(?:\s+#[a-zA-Z_0-9]+)*)\s*)?"', sXML)
  if M: return [M.group(3) if M.group(3) else "",
                M.group(2) if M.group(2) else "",
                float(M.group(4)) if M.group(4) else None,
                M.group(1) if M.group(1) else "",
                M.group(5) if M.group(5) else ""];  # ticker, date, DLSentiment, docID, tags
  M = re.search(r'<S_START [^>]*DLScore="([^"]+)"/>', sXML)
  if M: return ["", "", float(M.group(1)), "", ""]
  return ["", "", None, "", ""]



def TryParseJson(s):
  try:
    return json.loads(s)
  except:
    return None


def UnescapeHTML(s):
  return (re.sub(r'&#(\d+);', lambda M: chr(int(M.group(1))), s).
          replace('&quot;', "").
          replace('&gt', ">").replace('&lt;', "<").replace('&amp;', "&"))


def GetEventsDataFromXML(sXML):
  dDLSentiment = GetMetadataInfo(sXML)[2]
  eventsDataList = []
  for MEvent in reEvent.finditer(sXML):
    eventData = []  # [ [ slotName, slotValue, slotNormalizedValue ] ]  (slotNormalizedValue is optional)
    eventData.append([ 'EventText', re.sub(r'<[^>]*>', '', MEvent.group(2)) ])

    for MProp in reEventProp.finditer(MEvent.group(1)):
      sPropName = ('EventType' if MProp.group(1) == 'type' else
                   'Polarity'  if MProp.group(1) == 'polarity'  else  MProp.group(1))
      value = UnescapeHTML(MProp.group(2))
      if value[0] == '[' and value[-1] == ']':
        parsedValue = TryParseJson(value)
        if parsedValue is not None:
          for v in parsedValue:
            eventData.append([sPropName, v])
        else:
          eventData.append([ sPropName, value ])
      else:
        eventData.append([ sPropName, value ])

    for MSlot in reSlot.finditer(MEvent.group(2)):
      M = re.search(r'name="([^"]*)"', MSlot.group(1))
      if not M: continue
      sSlotName = M.group(1)
      sSlotValue = re.sub(r'<[^>]*>', '', MSlot.group(2))
      M = re.search(r'normalized="([^"]*)"', MSlot.group(1))
      if M:
        eventData.append([ sSlotName, UnescapeHTML(sSlotValue), UnescapeHTML(M.group(1)) ])
      else:
        eventData.append([ sSlotName, UnescapeHTML(sSlotValue), UnescapeHTML(sSlotValue) ])

    if dDLSentiment is not None:
      eventData.append([ 'DLPolarity', ('Positive' if dDLSentiment > 0 else 'Negative' if dDLSentiment < 0 else 'Neutral') ])
      eventData.append([ 'DLSentimentScore', str(dDLSentiment) ])

    eventsDataList.append(eventData)

  return eventsDataList



def GetEventPolarityFromEventData(eventData):
  for slotInfo in eventData:
    if slotInfo[0].lower() == "polarity":
      sValue = (slotInfo[2] or slotInfo[1]).lower()
      if sValue == "positive": return 1
      if sValue == "negative": return -1
  return 0



def GenerateCSVForMatches(matches, fUseExtraMetadata):
  if fUseExtraMetadata:
    if not GetExtraMetadataColumns():
      fUseExtraMetadata = False
    if fUseExtraMetadata:
      fUseExtraMetadata = False
      for theMatch in matches:
        sXML = theMatch[1]
        tickerDateDLScoreDocID = GetMetadataInfo(sXML)
        dateTickerDocID = tickerDateDLScoreDocID[1] + "," + tickerDateDLScoreDocID[0] + "," + tickerDateDLScoreDocID[3]
        if GetExtraMetadataColumnValues(dateTickerDocID):
          fUseExtraMetadata = True
          break

  def GetTagColumns(sTags):
    if not sTags: return None
    tagColumnValues = {}
    for sTag in re.split(r'\s+', sTags):
      M = re.match(r'^#(.+)_([^_]+)$', sTag)
      sColumn = M.group(1) if M else "Tags"
      sValue = M.group(2) if M else sTag
      if sColumn in tagColumnValues:
        tagColumnValues[sColumn] += ' ' + sValue
      else:
        tagColumnValues[sColumn] = sValue
    return tagColumnValues  #[...tagColumnValues].sort();

  tagColumnsSet = set()
  for theMatch in matches:
    sXML = theMatch[1]
    tagColumnValues = GetTagColumns(GetMetadataInfo(sXML)[4])
    if tagColumnValues:
      for sColumn in tagColumnValues:
        tagColumnsSet.add(sColumn)
  tagColumns = sorted(tagColumnsSet)
  tagColumnsMap = {c:i for i,c in enumerate(tagColumns)}

  columns = (["Sentence", "EventType", "Polarity", "Labeled", "Ticker", "DocDate", "DocID"]
              + tagColumns
              + (GetExtraMetadataColumns() if fUseExtraMetadata else []))
  column2Index = {c:i for i,c in enumerate(columns) if c == "EventType" or c == "Polarity"}

  rows = []
  for theMatch in matches:
    sXML = theMatch[1]
    sSent = re.sub(r'<[^>]*>', '', sXML)
    tickerDateDLScoreDocIDTags = GetMetadataInfo(sXML)
    dateTickerDocID = tickerDateDLScoreDocIDTags[1] + "," + tickerDateDLScoreDocIDTags[0] + "," + tickerDateDLScoreDocIDTags[3]
    tagColumnValues = [""] * len(tagColumns)
    tagColumnValuesMap = GetTagColumns(GetMetadataInfo(sXML)[4])
    if tagColumnValuesMap:
      for c, v in tagColumnValuesMap.items():
        tagColumnValues[tagColumnsMap[c]] = v

    for eventData in GetEventsDataFromXML(sXML):
      rowData = ([sSent, "", "", sXML, tickerDateDLScoreDocIDTags[0], tickerDateDLScoreDocIDTags[1], tickerDateDLScoreDocIDTags[3]]
                 + tagColumnValues
                 + (GetExtraMetadataColumnValues(dateTickerDocID) if fUseExtraMetadata else []))

      for slotInfo in eventData:
        iColumn = column2Index.get(slotInfo[0], -1)
        if iColumn < 0:
          iColumn = len(columns)
          columns.append(slotInfo[0])
          column2Index[slotInfo[0]] = iColumn
        slotValue = (slotInfo[2] if len(slotInfo) > 2 else "") or slotInfo[1]
        while len(rowData) <= iColumn: rowData.append("")
        if rowData[iColumn]:
          rowData[iColumn] += "|" + slotValue
        else:
          rowData[iColumn] = slotValue

      for i in range(len(rowData)):
        if rowData[i]:
          rowData[i] = MakeCSVField(rowData[i])

      rows.append(','.join(rowData))

  return ','.join(columns) + '\n' + '\n'.join(rows)


def Match2SentenceMatches(sHTML, sXML, fIncludeEmptySentences, processSentenceMatchFunc):
  sXML = re.sub(r'(<EVENT\b.*?>)(.*?)</EVENT>', lambda M: M.group(1) + re.sub(r'<[SP]_(START|END)\b[^>]*>', '', M.group(2)) + "</EVENT>", sXML)
  M = re.search('^(?:<P>)+(.*?)<SENT\b[^>]*>', sHTML)
  sHTMLPrefix = M.group(1) if M else ""
  HTMLs = re.findall(r'<SENT[^>]*>(.*?)</SENT>', sHTML)
  M = re.search(r'^(.*?)<P_START/>', sXML)
  sXMLPrefix = M.group(1) if M else ""
  XMLs = re.findall(r'<S_START[^>]*/>(.*?)<S_END/>', sXML)
  if len(HTMLs) != len(XMLs):
    print("Error: HTML and XML sentence counts differ: " + sHTML + " vs " + sXML, file=sys.stderr)
  for i in range(len(HTMLs)):
    if fIncludeEmptySentences or XMLs[i].find('<EVENT') != -1:
      processSentenceMatchFunc([sHTMLPrefix, HTMLs[i]], sXMLPrefix + "<P_START>" + XMLs[i] + "<P_END/>")



#------------ These are used by ProcessingAPI.py:

FM_AllMatches = []
FM_AllMatchesSentences2Index = {}
FM_AllRows = []

def AddNewMatchForFindMatches(sHTML, sXML):
  def Add(SentHTMLPieces, sSentXML):
    sent = re.sub(r'<[^>]*>', '', sSentXML)
    if sent not in FM_AllMatchesSentences2Index:
      FM_AllMatchesSentences2Index[sent] = len(FM_AllMatches)
      FM_AllMatches.append([SentHTMLPieces, sSentXML])
  Match2SentenceMatches(sHTML, sXML, False, Add)

def GetAllDocIDsForFindMatches():
  DocIDs = []
  for M in FM_AllMatches:
    DocIDs.append(GetMetadataInfo(M[1])[3])
  return DocIDs

def GenerateCSVForMatches_ProcessingAPI():
  return GenerateCSVForMatches(FM_AllMatches, True)

