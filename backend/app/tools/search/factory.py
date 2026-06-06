from app.tools.search.academic.arxiv_tool import ArxivTool
from app.tools.search.academic.google_scholar_tool import GoogleScholarTool
from app.tools.search.web.serpapi_web_tool import SerpAPIWebTool
from app.tools.search.academic.semantic_scholar_tool import SemanticScholarTool
from app.utils.constants import SearchSource

SEARCH_TOOL_REGISTRY = {
    SearchSource.ARXIV: ArxivTool,
    SearchSource.GOOGLE_SCHOLAR: GoogleScholarTool,
    SearchSource.WEB: SerpAPIWebTool,
    SearchSource.SEMANTIC_SCHOLAR: SemanticScholarTool,
}

class SearchToolFactory:
    @staticmethod
    def get_tool(source: SearchSource):
        tool_class = SEARCH_TOOL_REGISTRY.get(source)

        if not tool_class:
            raise ValueError(f"Unsupported search source: {source}")
        
        return tool_class()
    
    @staticmethod
    def get_tools(sources: list[SearchSource]):
        tools = []

        for source in sources:
            tool = SearchToolFactory.get_tool(source)
            tools.append(tool)
        
        return tools 
    
    @staticmethod
    def get_default_tools():
        # Default = academic-only sources. Generic Google web search adds a
        # lot of noise (blog posts, marketing pages, irrelevant Wikipedia
        # entries) when the query is a short token like a model name. Users
        # can still opt into web search by passing ``sources`` explicitly
        # to ``SearchService.search()``.
        return SearchToolFactory.get_tools([
            SearchSource.ARXIV,
            SearchSource.GOOGLE_SCHOLAR,
            SearchSource.SEMANTIC_SCHOLAR,
        ])