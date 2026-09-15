from dotenv import load_dotenv
from langchain_groq import ChatGroq


load_dotenv()


class ModelAdapter:
    """
    Provider-independent interface for TheAtom's language model.
    """

    def __init__(self, model):
        self.model = model

    def bind_tools(self, tools):
        return self.model.bind_tools(tools)

    def invoke(self, messages):
        return self.model.invoke(messages)


class GroqModel(ModelAdapter):
    """
    Groq implementation of the model adapter.
    """

    def __init__(self):
        model = ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0,
        )

        super().__init__(model)


model = GroqModel()