import asyncio
from examples.demo_workflow import DemoWorkflow
from examples.demo_activity import demo_activity


async def main():
    workflow = DemoWorkflow.compile()
    print(workflow)
    handle = await workflow.start(input={"message": "Hello, Mommy!"})

    print(f"Started workflow with ID: {handle.id}")
    print(f"Workflow status: {await handle.status()}")


asyncio.run(main())
