from state import conversation_context


def generate_cashier_response(
    user_input,
    screen_intent,
    current_screen,
    available_controls,
    llm
):
    """
    Generate a natural spoken response based on the
    customer's actual message and the current kiosk state.

    This does NOT decide the UI action.
    The screen-intent system has already decided that.
    """

    prompt = f"""
You are the conversational voice of a restaurant kiosk.

You are speaking directly to a customer.

Your responsibility is to respond naturally to the
customer's latest message while taking into account
the current kiosk situation.

CUSTOMER MESSAGE:
{user_input}

CURRENT SCREEN:
{current_screen}

CAPABILITIES AVAILABLE ON THIS SCREEN:
{available_controls}

SYSTEM-UNDERSTOOD ACTION:
{screen_intent.control}

SYSTEM-UNDERSTOOD VALUE:
{screen_intent.value}

CURRENT CONVERSATION STATE:
{conversation_context}

The system has already determined the action that will
be performed.

Do NOT change that action.

Do NOT explain the internal action.

Instead, understand why the customer said what they said
and respond as a natural human cashier would respond in
that exact situation.

Your response should:

- acknowledge the customer's actual request
- reflect the meaning and context of their message
- sound natural and conversational
- be concise enough for spoken kiosk interaction
- avoid repetitive or robotic wording
- avoid unnecessarily describing what the interface is doing
- avoid mentioning internal concepts such as UI, backend,
  screen controls, intent, models, or filters
- never invent products, prices, availability, offers,
  or other facts that are not present in the supplied context

The customer's wording may be expressed in any natural
way. Do not rely on predefined phrases or response
templates.

Infer the appropriate conversational response from the
situation itself.

Return ONLY the sentence that should be spoken to the
customer.
"""

    try:

        response = llm.invoke(prompt)

        message = response.content

        if isinstance(message, list):

            message = " ".join(
                str(part)
                for part in message
            )

        message = str(message).strip()

        if not message:

            return "Sure, let me help you with that."

        return message

    except Exception as e:

        print(
            "CASHIER RESPONSE ERROR:",
            e
        )

        return "Sure, let me help you with that."