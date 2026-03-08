#Defining the intents of the customer and the actions to be taken by the system based on those intents.

def route_intent(intent):
    
    if intent.action == "greeting":
        return "llm"

    elif intent.action == "show_menu":
        return "menu"

    elif intent.action == "add_item":
        return "order"

    elif intent.action == "checkout":
        return "checkout"

    else:
        return "llm"