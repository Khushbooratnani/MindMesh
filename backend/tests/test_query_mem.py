import asyncio
from sqlalchemy import select
from app.database.connection.session import get_session_maker
from app.database.models.phase1_output import Phase1OutputModel

async def test():
    maker = get_session_maker()
    async with maker() as session:
        stmt = select(Phase1OutputModel).where(Phase1OutputModel.memory_id == 'M_0231b42d00624df5b0c7bdc485928acf')
        res = await session.execute(stmt)
        mem = res.scalar_one_or_none()
        print('FOUND:', mem.memory_id if mem else 'NOT FOUND')

asyncio.run(test())
