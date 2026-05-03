import mlflow
mlflow.set_tracking_uri("http://localhost:5000")
experiments = mlflow.search_experiments()
for exp in experiments:
    print(f"ID: {exp.experiment_id}, Name: {exp.name}")
