import chainlit as cl
import dotenv

from openai.types.responses import ResponseTextDeltaEvent
from agents import Runner, SQLiteSession
from meal_advisor import meal_advisor, init_mcp

# Load environment variables
dotenv.load_dotenv()

# Chart Start Event
@cl.on_chat_start
async def on_chat_start():
    # Initialize MCP (connect to Exa)
    await init_mcp()

    # Set up SQLite session for conversation history
    session = SQLiteSession("conversation_history")
    cl.user_session.set("agent_session", session)

    # Send introduction message to users
    await cl.Message(
        content=(
            "**Welcome to Meal Advisor!**\n\n"
            "I'm your AI-powered breakfast assistant 🍳. "
            "I can help you plan **healthy, affordable, and delicious breakfasts** "
            "based on your preferences. You can ask things like:\n\n"
            "• *Suggest two healthy oatmeal breakfasts for busy mornings.*\n"
            "• *What's the calorie count of an egg sandwich?*\n\n"
            "Let's start your day right!"
        )
    ).send()

# Message Event
@cl.on_message
async def on_message(message: cl.Message):
    session = cl.user_session.get("agent_session")

    result = Runner.run_streamed(meal_advisor, message.content, session=session)

    msg = cl.Message(content="")
    async for event in result.stream_events():
        # Stream final message text to screen
        if event.type == "raw_response_event" and isinstance(
            event.data, ResponseTextDeltaEvent
        ):
            await msg.stream_token(token=event.data.delta)

        elif (
            event.type == "raw_response_event"
            and hasattr(event.data, "item")
            and hasattr(event.data.item, "type")
            and event.data.item.type == "function_call"
            and len(event.data.item.arguments) > 0
        ):
            with cl.Step(name=f"{event.data.item.name}", type="tool") as step:
                step.input = event.data.item.arguments

    await msg.update()