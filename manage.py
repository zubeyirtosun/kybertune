import inquirer
import yaml
import os
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def get_current_value(file_path, key_type):
    if not os.path.exists(file_path):
        return ""
    with open(file_path, 'r') as f:
        docs = list(yaml.safe_load_all(f))
    
    for doc in docs:
        if not doc: continue
        if key_type == 'repoURL' and doc.get('kind') == 'Application':
            return doc['spec']['source'].get('repoURL', "")
        if doc.get('kind') == 'Deployment':
            for container in doc['spec']['template']['spec']['containers']:
                for env in container.get('env', []):
                    if env['name'] == key_type:
                        return env.get('value', "")
    return ""

def update_yaml(file_path, updates):
    if not os.path.exists(file_path):
        return False
    
    with open(file_path, 'r') as f:
        content = list(yaml.safe_load_all(f))

    for doc in content:
        if not doc: continue
        if doc.get('kind') == 'Application':
            if 'repoURL' in updates:
                doc['spec']['source']['repoURL'] = updates['repoURL']
        
        if doc.get('kind') == 'Deployment':
            for container in doc['spec']['template']['spec']['containers']:
                for env in container.get('env', []):
                    if env['name'] == 'RUN_ID' and 'RUN_ID' in updates:
                        env['value'] = updates['RUN_ID']
                    if env['name'] == 'MODEL_ID' and 'MODEL_ID' in updates:
                        env['value'] = updates['MODEL_ID']

    with open(file_path, 'w') as f:
        yaml.safe_dump_all(content, f, default_flow_style=False)
    return True

def main():
    console.print(Panel.fit("[bold cyan]KyberTune Control Center[/bold cyan]", subtitle="v1.2 - UX Enhanced"))

    menu = [
        inquirer.List('action',
                      message="Ne yapmak istersiniz?",
                      choices=[
                          ('ArgoCD Repo URL Güncelle', 'update_git'),
                          ('Serving RUN_ID Güncelle', 'update_run'),
                          ('Eğitim Modelini Değiştir', 'update_model'),
                          ('Sistem Durumunu Gör', 'status'),
                          ('Altyapıyı Kubernetes\'e Uygula (Sync)', 'sync'),
                          ('Çıkış', 'exit')
                      ],
                      ),
    ]

    answers = inquirer.prompt(menu)
    if not answers: return

    if answers['action'] == 'update_git':
        current = get_current_value('infrastructure/argocd-app.yaml', 'repoURL')
        url = inquirer.text(message="GitHub Repo URL giriniz", default=current)
        if update_yaml('infrastructure/argocd-app.yaml', {'repoURL': url}):
            console.print("[green]✔[/green] ArgoCD manifesti güncellendi!")
            if inquirer.confirm("Bu değişikliği hemen Kubernetes'e uygulayalım mı?"):
                success, out = run_command("kubectl apply -f infrastructure/argocd-app.yaml")
                if success: console.print("[green]✔[/green] ArgoCD uygulaması başarıyla oluşturuldu/güncellendi!")
                else: console.print(f"[red]! Hata:[/red] {out}")
        
    elif answers['action'] == 'update_run':
        current = get_current_value('infrastructure/serving-deployment.yaml', 'RUN_ID')
        console.print(f"[blue]Mevcut RUN_ID:[/blue] [bold]{current}[/bold]")
        try:
            import mlflow
            mlflow.set_tracking_uri("http://localhost:5000")
            experiment = mlflow.get_experiment_by_name("KyberTune-FineTuning")
            if experiment:
                runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id], max_results=5)
                choices = [(f"{run['tags.mlflow.runName']} ({run['start_time'].strftime('%m-%d %H:%M')})", run['run_id']) for _, run in runs.iterrows()]
                if choices:
                    run_answers = inquirer.prompt([inquirer.List('run_id', message="Hangi eğitimi yayına almak istersiniz?", choices=choices, default=current)])
                    run_id = run_answers['run_id']
                else: run_id = inquirer.text(message="Eğitim bulunamadı, manuel ID girin", default=current)
            else: run_id = inquirer.text(message="Deney bulunamadı, manuel ID girin", default=current)
        except:
            run_id = inquirer.text(message="MLflow bağlantısı yok, manuel ID girin", default=current)

        if update_yaml('infrastructure/serving-deployment.yaml', {'RUN_ID': run_id}):
            console.print(f"[green]✔[/green] Lokal dosya güncellendi.")
            console.print("[yellow]! Hatırlatma: GitOps devredeyse değişikliği GitHub'a pushlamayı unutmayın.[/yellow]")

    elif answers['action'] == 'update_model':
        current = get_current_value('infrastructure/serving-deployment.yaml', 'MODEL_ID') # Check from serving too
        model = inquirer.text(message="Model ID giriniz (HuggingFace)", default=current or "microsoft/Phi-3-mini-4k-instruct")
        if update_yaml('infrastructure/serving-deployment.yaml', {'MODEL_ID': model}): # Update serving deployment too
             console.print("[green]✔[/green] Manifest güncellendi!")

    elif answers['action'] == 'sync':
        console.print("[blue]Altyapı senkronize ediliyor...[/blue]")
        success, out = run_command("kubectl apply -f infrastructure/argocd-app.yaml")
        if success: console.print("[green]✔[/green] ArgoCD Application aktif!")
        else: console.print(f"[red]! Hata:[/red] {out}")

    elif answers['action'] == 'status':
        table = Table(title="KyberTune Altyapı Durumu")
        table.add_column("Bileşen", style="cyan")
        table.add_column("Durum", style="magenta")
        
        k8s_ok, _ = run_command("kubectl get nodes")
        argocd_ok, _ = run_command("kubectl get app -n argocd kybertune-llmops")
        
        table.add_row("Kubernetes (Kind)", "[green]Aktif[/green]" if k8s_ok else "[red]Bağlantı Yok[/red]")
        table.add_row("ArgoCD App", "[green]Kurulu[/green]" if argocd_ok else "[yellow]Beklemede[/yellow]")
        table.add_row("MLflow", "Erişilebilir (Port 5000)")
        
        console.print(table)

    elif answers['action'] == 'exit':
        console.print("[yellow]Güle güle![/yellow]")

if __name__ == "__main__":
    main()
