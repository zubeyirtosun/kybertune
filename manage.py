import inquirer
import yaml
import os
import subprocess
import time
import socket
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

def run_command(command, background=False):
    try:
        if background:
            os.makedirs('logs', exist_ok=True)
            with open('logs/port_forward.log', 'a') as log:
                subprocess.Popen(command, shell=True, stdout=log, stderr=log)
            return True, "Başlatıldı"
        else:
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            return True, result.stdout
    except Exception as e:
        return False, str(e)

def load_ports():
    if not os.path.exists('ports.yaml'):
        return {'mlflow': {'local': 5000, 'remote': 5000}, 'argocd': {'local': 8080, 'remote': 443}, 'ui': {'local': 8501, 'remote': 8501}, 'serving': {'local': 8000, 'remote': 8000}}
    with open('ports.yaml', 'r') as f:
        return yaml.safe_load(f)

def save_ports(ports):
    with open('ports.yaml', 'w') as f:
        yaml.safe_dump(ports, f)

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('localhost', int(port))) == 0

def get_current_value(file_path, key_type):
    if not os.path.exists(file_path): return ""
    with open(file_path, 'r') as f:
        try:
            docs = list(yaml.safe_load_all(f))
            for doc in docs:
                if not doc: continue
                if key_type == 'repoURL' and doc.get('kind') == 'Application':
                    return doc['spec']['source'].get('repoURL', "")
                if doc.get('kind') == 'Deployment':
                    for container in doc['spec']['template']['spec']['containers']:
                        for env in container.get('env', []):
                            if env['name'] == key_type: return env.get('value', "")
        except: pass
    return ""

def update_yaml(file_path, updates):
    if not os.path.exists(file_path): return False
    with open(file_path, 'r') as f:
        content = list(yaml.safe_load_all(f))
    for doc in content:
        if not doc: continue
        if doc.get('kind') == 'Application' and 'repoURL' in updates:
            doc['spec']['source']['repoURL'] = updates['repoURL']
        if doc.get('kind') == 'Deployment':
            for container in doc['spec']['template']['spec']['containers']:
                for env in container.get('env', []):
                    if env['name'] in updates:
                        env['value'] = updates[env['name']]
    with open(file_path, 'w') as f:
        yaml.safe_dump_all(content, f, default_flow_style=False)
    return True

def startup_system():
    ports = load_ports()
    console.print("[yellow]Sistem bağlantıları kuruluyor...[/yellow]")
    run_command("pkill -f 'kubectl port-forward'")
    time.sleep(1)
    forwards = [
        ("svc/mlflow-service", f"{ports['mlflow']['local']}:{ports['mlflow']['remote']}", "kybertune"),
        ("svc/minio-service", "9000:9000", "kybertune"),
        ("svc/minio-service", "9001:9001", "kybertune"),
        ("svc/argocd-server", f"{ports['argocd']['local']}:80", "argocd"),
        ("svc/ui-service", f"{ports['ui']['local']}:{ports['ui']['remote']}", "kybertune")
    ]
    for target, p, ns in forwards:
        console.print(f"[blue]→ {target} ({p}) açılıyor...[/blue]")
        run_command(f"kubectl port-forward -n {ns} {target} {p} --address 0.0.0.0", background=True)
    time.sleep(2)
    console.print("[green]✔ Başlatma komutları gönderildi.[/green]")

def main():
    console.print(Panel.fit("[bold cyan]KyberTune Control Center[/bold cyan]", subtitle="v1.5 - Bug Fixed & Full Auto"))
    menu = [
        inquirer.List('action',
                      message="Ne yapmak istersiniz?",
                      choices=[
                          ('Sistemi Uyandır (Bağlantıları Kur)', 'startup'),
                          ('Sistem Durumunu Gör (Health Check)', 'status'),
                          ('Modeli Eğit (Fine-Tuning)', 'run_training'),
                          ('Modeli Başlat (GPU - Serving)', 'start_serving'),
                          ('Web UI Yayına Al/Güncelle', 'deploy_ui'),
                          ('Port Yapılandırmasını Yönet', 'ports'),
                          ('ArgoCD Repo URL Güncelle', 'update_git'),
                          ('Çıkış', 'exit')
                      ],
                      ),
    ]
    answers = inquirer.prompt(menu)
    if not answers: return

    if answers['action'] == 'startup':
        startup_system()

    elif answers['action'] == 'run_training':
        console.print(Panel.fit("[bold yellow]Fine-Tuning Konfigürasyonu[/bold yellow]"))
        train_questions = [
            inquirer.Text('model_id',
                          message="Model ID (HuggingFace)",
                          default="microsoft/Phi-3-mini-4k-instruct"),
            inquirer.Text('dataset_path',
                          message="Dataset yolu (JSONL)",
                          default="data/dataset.jsonl"),
            inquirer.Text('max_steps',
                          message="Max adım sayısı",
                          default="10"),
            inquirer.Text('batch_size',
                          message="Batch size",
                          default="1"),
            inquirer.Text('learning_rate',
                          message="Learning rate",
                          default="2e-4"),
            inquirer.Text('lora_r',
                          message="LoRA rank (r)",
                          default="8"),
        ]
        train_cfg = inquirer.prompt(train_questions)
        if not train_cfg: return

        # Build image if not present
        console.print("[yellow]Training image kontrol ediliyor...[/yellow]")
        ok, out = run_command("docker image inspect kybertune-training:latest -f '{{.Id}}'")
        if not ok:
            console.print("[yellow]Training image bulunamadı, build ediliyor...[/yellow]")
            ok, out = run_command("sudo docker build -t kybertune-training:latest -f training/Dockerfile .")
            if not ok:
                console.print(f"[red]Build hatası:[/red] {out}")
                return

        mlflow_uri = "http://172.18.0.1:5000"
        hf_cache = os.path.expanduser("~/.cache/huggingface")
        results_path = os.path.abspath("results")
        os.makedirs(results_path, exist_ok=True)

        cmd = (
            f"sudo docker run --rm --gpus all "
            f"--name kybertune-training "
            f"-v {hf_cache}:/root/.cache/huggingface "
            f"-v {results_path}:/app/results "
            f"-e MLFLOW_TRACKING_URI={mlflow_uri} "
            f"-e MLFLOW_S3_ENDPOINT_URL=http://172.18.0.1:9000 "
            f"-e AWS_ACCESS_KEY_ID=admin "
            f"-e AWS_SECRET_ACCESS_KEY=admin123 "
            f"-e MLFLOW_S3_IGNORE_TLS=true "
            f"-e MODEL_ID={train_cfg['model_id']} "
            f"-e DATASET_PATH={train_cfg['dataset_path']} "
            f"-e MAX_STEPS={train_cfg['max_steps']} "
            f"-e BATCH_SIZE={train_cfg['batch_size']} "
            f"-e LEARNING_RATE={train_cfg['learning_rate']} "
            f"-e LORA_R={train_cfg['lora_r']} "
            f"kybertune-training:latest"
        )
        console.print("[yellow]Eğitim başlıyor... (MLflow: http://localhost:5000)[/yellow]")
        success, out = run_command(cmd)
        if success:
            console.print("[green]✔ Eğitim tamamlandı! MLflow'dan sonuçları inceleyin:[/green]")
            console.print("  → http://localhost:5000")
        else:
            console.print(f"[red]Hata:[/red] {out}")

    elif answers['action'] == 'start_serving':
        current_run = get_current_value('infrastructure/serving-deployment.yaml', 'RUN_ID')
        try:
            import mlflow
            mlflow.set_tracking_uri("http://localhost:5000")
            experiment = mlflow.get_experiment_by_name("KyberTune-FineTuning")
            runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id], max_results=5)
            choices = [(f"{run['tags.mlflow.runName']} ({run['start_time'].strftime('%m-%d %H:%M')})", run['run_id']) for _, run in runs.iterrows()]
            run_id = inquirer.prompt([inquirer.List('run_id', message="Seçiniz", choices=choices, default=current_run)])['run_id']
        except: run_id = inquirer.text(message="Manuel RUN_ID", default=current_run)
        
        # 2. Host Seçimi
        host_ans = inquirer.prompt([
            inquirer.List('host', 
                          message="Model hangi adreste yayınlansın?", 
                          choices=[('Tüm Ağ (0.0.0.0) - Önerilen', '0.0.0.0'), ('Sadece Yerel (127.0.0.1)', '127.0.0.1')],
                          default='0.0.0.0')
        ])
        host = host_ans['host']

        # 3. Temizlik ve Başlatma
        console.print("[yellow]Eski servisler durduruluyor ve model hazırlanıyor...[/yellow]")
        run_command("sudo docker stop kybertune-serving")
        cmd = (
            f"sudo docker run -d --rm --runtime=nvidia --gpus all "
            f"--name kybertune-serving "
            f"-v $HOME/.cache/huggingface:/root/.cache/huggingface "
            f"-p 8000:8000 "
            f"-e MLFLOW_TRACKING_URI=http://172.18.0.1:5000 "
            f"-e RUN_ID={run_id} "
            f"kybertune-serving:latest"
        )
        success, out = run_command(cmd)
        if success:
            console.print(f"[green]✔ Model Başlatıldı! (RUN_ID: {run_id})[/green]")
            console.print("[blue]Modelin ayağa kalkması bir miktar sürebilir. UI üzerinden test edebilirsiniz.[/blue]")
        else:
            console.print(f"[red]! Hata:[/red] {out}")

    elif answers['action'] == 'deploy_ui':
        success, _ = run_command("sudo docker build -t kybertune-ui:latest -f ui/Dockerfile .")
        if success:
            run_command("kind load docker-image kybertune-ui:latest --name kybertune-cluster")
            run_command("kubectl apply -f infrastructure/argocd-sync/ui-deployment.yaml")
            run_command("kubectl delete pod -n kybertune -l app=ui")
            console.print("[green]✔ UI Güncellendi.[/green]")

    elif answers['action'] == 'status':
        ports = load_ports()
        table = Table(title="KyberTune Sağlık Kontrolü")
        table.add_column("Bileşen", style="cyan"); table.add_column("Port", style="yellow"); table.add_column("Durum", style="magenta")
        k8s_ok, _ = run_command("kubectl get nodes")
        table.add_row("Kubernetes (Kind)", "-", "[green]Aktif[/green]" if k8s_ok else "[red]Down[/red]")
        table.add_row("MLflow Tracking", str(ports['mlflow']['local']), "[green]Erişilebilir[/green]" if check_port(ports['mlflow']['local']) else "[red]Kapalı[/red]")
        table.add_row("ArgoCD UI", str(ports['argocd']['local']), "[green]Erişilebilir[/green]" if check_port(ports['argocd']['local']) else "[red]Kapalı[/red]")
        table.add_row("Web UI Chat", str(ports['ui']['local']), "[green]Erişilebilir[/green]" if check_port(ports['ui']['local']) else "[red]Kapalı[/red]")
        console.print(table)

    elif answers['action'] == 'update_git':
        current = get_current_value('infrastructure/argocd-app.yaml', 'repoURL')
        url = inquirer.text(message="Repo URL", default=current)
        if update_yaml('infrastructure/argocd-app.yaml', {'repoURL': url}):
            if inquirer.confirm("Kubernetes'e uygulansın mı?"): run_command("kubectl apply -f infrastructure/argocd-app.yaml")

    elif answers['action'] == 'exit':
        console.print("[yellow]Güle güle![/yellow]")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: console.print("\n[yellow]İptal edildi.[/yellow]")
