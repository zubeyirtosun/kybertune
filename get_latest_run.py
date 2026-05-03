import mlflow
import os

mlflow.set_tracking_uri("http://localhost:5000")
try:
    experiment = mlflow.get_experiment_by_name("KyberTune-FineTuning")
    if experiment:
        runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id], max_results=1, order_by=["start_time DESC"])
        if not runs.empty:
            print(runs.iloc[0]["run_id"])
        else:
            print("NONE")
    else:
        print("NONE")
except Exception as e:
    print(f"ERROR: {e}")
