import os

KNOWLEDGE_PATH = "knowledge"


def get_relevant_knowledge(user_input, llm):

    docs = []

    for file in os.listdir(KNOWLEDGE_PATH):
        if file.endswith(".txt"):
            with open(os.path.join(KNOWLEDGE_PATH, file), "r") as f:
                docs.append(f.read())

    prompt = f"""
Customer asked:
{user_input}

Choose only the most relevant product knowledge below:

{docs}

Return only relevant knowledge.
"""

    response = llm.invoke(prompt)

    return response.content