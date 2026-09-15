from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
)


class AgentRuntime:
    """
    Provider-independent orchestration layer for TheAtom's cashier agent.
    """

    def __init__(
        self,
        model,
        tools_factory,
        system_prompt,
    ):
        self.model = model
        self.tools_factory = tools_factory
        self.system_prompt = system_prompt

    def run(
        self,
        user_input,
        conversation_context,
        customer_context,
        history,
    ):
        tools = self.tools_factory(
            conversation_context
        )

        llm_with_tools = self.model.bind_tools(
            tools
        )

        tool_map = {
            tool.name: tool
            for tool in tools
        }

        messages = [
            SystemMessage(
                content=self.system_prompt
            ),
            SystemMessage(
                content=f"""
CURRENT CUSTOMER CONTEXT:

{customer_context}
"""
            ),
        ]

        messages.extend(history)

        messages.append(
            HumanMessage(
                content=user_input
            )
        )

        response = llm_with_tools.invoke(
            messages
        )

        messages.append(response)

        while response.tool_calls:

            print("\nAGENT TOOL CALLS:")
            print(response.tool_calls)

            for tool_call in response.tool_calls:

                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]

                print(
                    f"\nEXECUTING TOOL: {tool_name}"
                )

                print(
                    f"TOOL ARGS: {tool_args}"
                )

                selected_tool = tool_map.get(
                    tool_name
                )

                if not selected_tool:

                    tool_result = {
                        "error": (
                            f"Tool '{tool_name}' not found."
                        )
                    }

                else:

                    try:
                        tool_result = selected_tool.invoke(
                            tool_args
                        )

                    except Exception as exc:

                        tool_result = {
                            "error": str(exc)
                        }

                print("\nTOOL RESULT:")
                print(tool_result)

                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call_id,
                    )
                )

            response = llm_with_tools.invoke(
                messages
            )

            messages.append(response)

        conversation_messages = []

        for message in messages:

            if isinstance(
                message,
                (
                    HumanMessage,
                    AIMessage,
                    ToolMessage,
                ),
            ):
                conversation_messages.append(
                    message
                )

        conversation_context[
            "conversation_history"
        ] = conversation_messages

        return response.content
