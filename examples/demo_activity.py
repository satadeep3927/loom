from src.decorators.activity import activity


@activity(
    name="DemoActivity",
    description="A demo activity for showcasing functionality.",
)
async def demo_activity():
    print("Executing the demo activity...")
    return "Satadeep"
