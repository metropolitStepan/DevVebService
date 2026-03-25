import asyncio
import time
from typing import Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


Number = Union[int, float]


class CalculateRequest(BaseModel):
    numbers: list[Number] = Field(..., min_length=1, description="Список чисел")
    delays: list[float] = Field(..., min_length=1, description="Список задержек в секундах")


class CalculationResult(BaseModel):
    number: Number
    square: Number
    delay: float
    time: float


class CalculateResponse(BaseModel):
    results: list[CalculationResult]
    total_time: float
    parallel_faster_than_sequential: bool


app = FastAPI(title="Calculate API")


async def calculate_square(number: Number, delay: float) -> tuple[CalculationResult, float]:
    start_time = time.perf_counter()
    await asyncio.sleep(delay)
    elapsed = time.perf_counter() - start_time

    return (
        CalculationResult(
            number=number,
            square=number * number,
            delay=delay,
            time=round(elapsed, 2),
        ),
        elapsed,
    )


@app.post("/calculate/", response_model=CalculateResponse)
async def calculate(data: CalculateRequest) -> CalculateResponse:
    if len(data.numbers) != len(data.delays):
        raise HTTPException(
            status_code=422,
            detail="Количество чисел и задержек должно совпадать.",
        )

    if any(delay < 0 for delay in data.delays):
        raise HTTPException(
            status_code=422,
            detail="Задержки не могут быть отрицательными.",
        )

    start_time = time.perf_counter()
    task_results = await asyncio.gather(
        *(calculate_square(number, delay) for number, delay in zip(data.numbers, data.delays))
    )
    total_time_raw = time.perf_counter() - start_time
    results = [result for result, _ in task_results]
    sequential_time_raw = sum(elapsed for _, elapsed in task_results)

    return CalculateResponse(
        results=results,
        total_time=round(total_time_raw, 2),
        parallel_faster_than_sequential=total_time_raw < sequential_time_raw,
    )
