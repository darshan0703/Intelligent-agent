from services.cashier_agent import run_cashier_agent
from state import (
    reset_conversation,
    conversation_context
)


reset_conversation()


while True:

    user_input = input("\nCUSTOMER: ")

    if user_input.lower() == "exit":
        break


    response = run_cashier_agent(
        user_input,
        conversation_context
    )


    print("\nCASHIER:")
    print(response)