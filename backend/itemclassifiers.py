def resolve_burger_clarification(answer, llm):

    prompt = f"""
You are resolving a burger clarification answer.

Possible outputs:
veg
non veg
both
new_intent
unknown

Customer answer:
{answer}

Rules:

- veg = customer wants veg burgers
- non veg = customer wants non veg burgers
- both = customer wants both veg and non veg
- new_intent = customer switched to ordering something else
- unknown = unclear answer

Return only one word.
"""

    result = llm.invoke(prompt).content.strip().lower()

    return result