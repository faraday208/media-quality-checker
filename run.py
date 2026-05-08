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
