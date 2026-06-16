import os

KNOWLEDGE_PATH = "knowledge"


def get_relevant_knowledge(user_input, llm):

    candidate_docs = []

    for file in os.listdir(KNOWLEDGE_PATH):
        if file.endswith(".txt"):
            with open(os.path.join(KNOWLEDGE_PATH, file), "r") as f:
                content = f.read()

                if any(word in content.lower() for word in user_input.lower().split()):
                    candidate_docs.append(content)

    if not candidate_docs:
        candidate_docs = []

        for file in os.listdir(KNOWLEDGE_PATH):
            if file.endswith(".txt"):
                with open(os.path.join(KNOWLEDGE_PATH, file), "r") as f:
                    candidate_docs.append(f.read())

    prompt = f"""
Customer asked:
{user_input}

Choose only the most relevant product knowledge below.

Return only the most relevant item knowledge.

Knowledge:
{candidate_docs}
"""

    response = llm.invoke(prompt)

    return response.content