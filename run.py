#!/usr/bin/env python3
"""
Image Quality Checker - CLI Runner
"""

import click
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config" / "settings.yaml"


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


@click.group()
def cli():
    """Image Quality Checker - Blur, Brightness, Contrast, BPP kontrolü."""
    pass


@cli.command()
@click.option('--host', default=None, help='API host')
@click.option('--port', default=None, type=int, help='API port')
def api(host, port):
    """FastAPI sunucusunu başlat."""
    import uvicorn

    config = load_config()
    server_config = config.get('server', {})

    host = host or server_config.get('host', '0.0.0.0')
    port = port or server_config.get('port', 8101)

    click.echo(f"Starting Image Quality Checker API on {host}:{port}")
    uvicorn.run("api.main:app", host=host, port=port, reload=False)


@cli.command()
@click.argument('image_path')
@click.option('--check', '-c', multiple=True,
              type=click.Choice(['blur', 'brightness', 'contrast', 'bpp', 'all']),
              default=['all'], help='Kontrol türü')
def check(image_path, check):
    """Tek görüntü kontrolü."""
    from src.checkers import BlurChecker, BrightnessChecker, ContrastChecker, BPPChecker

    config = load_config()
    checks = list(check)

    if 'all' in checks:
        checks = ['blur', 'brightness', 'contrast', 'bpp']

    results = {}

    if 'blur' in checks:
        checker = BlurChecker(config)
        results['blur'] = checker.check(image_path).to_dict()

    if 'brightness' in checks:
        checker = BrightnessChecker(config)
        results['brightness'] = checker.check(image_path).to_dict()

    if 'contrast' in checks:
        checker = ContrastChecker(config)
        results['contrast'] = checker.check(image_path).to_dict()

    if 'bpp' in checks:
        checker = BPPChecker(config)
        results['bpp'] = checker.check(image_path).to_dict()

    import json
    click.echo(json.dumps(results, indent=2))


if __name__ == '__main__':
    cli()
