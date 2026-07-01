from schemas import ClarificationDecision

def resolve_burger_clarification(answer, llm):

    structured_llm = llm.with_structured_output(
        ClarificationDecision
    )

    prompt = f"""
You are resolving a burger clarification answer.

Context:
The cashier previously asked:

"Would you like veg, non veg, or both?"

Determine whether the customer:

1. Answered the question
2. Started a new request
3. Gave an unclear answer

Rules:

If the customer answered:

Veg examples:
- veg
- vegetarian
- veggie
- no meat

Return:

action = clarification_answer
value = veg

Non Veg examples:
- non veg
- chicken
- meat

Return:

action = clarification_answer
value = non veg

Both examples:
- both
- either
- any

Return:

action = clarification_answer
value = both

If customer started a new request:

Examples:
- show drinks
- show desserts
- i want a burger
- add fries
- checkout

Return:

action = new_intent

If unclear:

Examples:
- maybe
- not sure
- hmm

Return:

action = unclear

Customer:
{answer}
"""

    return structured_llm.invoke(prompt)