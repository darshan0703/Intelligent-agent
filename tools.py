from datetime import datetime
from langchain.tools import Tool
from langchain_community.tools import DuckDuckGoSearchRun

search = DuckDuckGoSearchRun()
search_tool = Tool(
    func=search.run, 
    name="DuckDuckGo_Search", 
    description="useful for when you need to answer questions about current events. You should ask targeted questions")

