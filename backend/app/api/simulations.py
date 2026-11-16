from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_current_active_user
from app.db import get_db
from app.models.models import Simulation, User
from app.schemas.schemas import SimulationApprovalInput, SimulationInput, SimulationOut
from app.services.simulation_engine import approve_simulation, cancel_simulation, simulate_decision

router = APIRouter()


def _simulation_response(simulation: Simulation) -> dict:
    return {
        "id": simulation.id,
        "user_id": simulation.user_id,
        "title": simulation.title,
        "scenario_type": simulation.scenario_type,
        "original_snapshot": simulation.original_snapshot,
        "proposed_snapshot": simulation.proposed_snapshot,
        "impact_analysis": simulation.impact_analysis,
        "feasibility_result": simulation.feasibility_result,
        "status": simulation.status,
        "created_at": simulation.created_at,
        "updated_at": simulation.updated_at,
        "alternatives": simulation.alternatives,
    }


@router.post("/run", response_model=SimulationOut)
def run_simulation(
    payload: SimulationInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        simulation, _ = simulate_decision(
            db,
            current_user,
            payload.task_id,
            payload.scenario_type,
            new_time=payload.new_time,
            new_duration=payload.new_duration,
            new_priority=payload.new_priority,
            move_to_date=payload.move_to_date,
        )
    except ValueError as exc:
        status_code = 404 if str(exc) == "Task not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    db.refresh(simulation)
    return _simulation_response(simulation)


@router.get("/history", response_model=list[SimulationOut])
def get_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    simulations = (
        db.query(Simulation)
        .options(selectinload(Simulation.alternatives))
        .filter(Simulation.user_id == current_user.id)
        .order_by(Simulation.created_at.desc())
        .all()
    )
    return [_simulation_response(simulation) for simulation in simulations]


@router.post("/{simulation_id}/approve")
def approve(
    simulation_id: int,
    payload: SimulationApprovalInput | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        return approve_simulation(
            db,
            current_user,
            simulation_id,
            alternative_id=payload.alternative_id if payload else None,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{simulation_id}/cancel")
def cancel(
    simulation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        return cancel_simulation(db, current_user, simulation_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
