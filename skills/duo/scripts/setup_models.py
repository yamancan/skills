#!/usr/bin/env python3
"""Inspect or explicitly save future-task model choices. No provider calls or credentials."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True

from session_store import index, is_versioned_model, state_dir, write_json

CATALOG = json.loads((Path(__file__).resolve().parents[1]/'references/models.json').read_text())
EFFORTS = {'codex': ('low', 'medium', 'high', 'xhigh', 'max', 'ultra'),
           'astra': ('low', 'medium', 'high', 'xhigh', 'max', 'ultra'),
           'opus': ('low', 'medium', 'high', 'xhigh', 'max'),
           'fable': ('low', 'medium', 'high', 'xhigh', 'max')}
CLI = {'codex': 'codex', 'astra': 'codex', 'opus': 'claude', 'fable': 'claude'}


def configured():
    path = state_dir()/'models.json'
    data = json.loads(path.read_text()) if path.exists() else {'profiles': {}}
    if not isinstance(data, dict) or not isinstance(data.get('profiles'), dict):
        raise ValueError('Invalid model configuration; inspect models.json before changing it.')
    return data


def selections(profile):
    catalog = CATALOG
    saved = configured()
    choices = deepcopy(saved['profiles'].get(profile, catalog['profiles'][profile]))
    # Older normal profiles predate the explicit Duo peer seat.
    if profile == 'normal' and isinstance(choices, dict) and 'opus' not in choices:
        choices['opus'] = deepcopy(catalog['profiles'][profile]['opus'])
    validate(profile, choices)
    return choices


def validate(profile, choices):
    roles = CATALOG['profiles'][profile]
    if not isinstance(choices, dict) or choices.keys() != roles.keys():
        raise ValueError('Model roles disagree with the selected profile.')
    for role, choice in choices.items():
        if not isinstance(choice, dict):
            raise ValueError('Invalid model selection.')
        model, effort = choice.get('model', ''), choice.get('effort')
        if not is_versioned_model(model):
            raise ValueError('Use an explicit versioned model ID, not a mutable latest/opus alias.')
        if effort not in EFFORTS[role]:
            raise ValueError(f'{role} effort must be one of: {", ".join(EFFORTS[role])}.')
        if role in ('opus', 'fable') and role not in model.lower():
            raise ValueError(f'{role} requires the selected {role} family, not a substitute.')
        if profile == 'duo' and effort != 'xhigh':
            raise ValueError('The Duo dispatcher supports xhigh on both seats; use another workflow for other efforts.')


def selected_peer(owner):
    if 'duo' not in configured()['profiles']:
        raise ValueError('Select the peer model explicitly or run Duo setup.sh first.')
    return selections('duo')['opus' if owner == 'codex' else 'codex']['model']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('duo', 'normal'), default='duo')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--check', action='store_true', help='Read-only local report; no CLI execution/network/writes.')
    action.add_argument('--save', action='store_true', help='Explicitly save choices for future tasks; never edits pairs.')
    action.add_argument('--rows', action='store_true', help='Tab-separated existing/default choices for the setup wizard.')
    parser.add_argument('--set', action='append', default=[], metavar='ROLE=MODEL:EFFORT')
    args = parser.parse_args()
    try:
        choices = selections(args.profile)
        for update in args.set:
            role, selection = update.split('=', 1)
            model, effort = selection.rsplit(':', 1)
            if role not in choices:
                raise ValueError('Unknown role for the selected profile.')
            choices[role] = {'model': model, 'effort': effort}
        validate(args.profile, choices)
        if args.save:
            # Use the existing shared lock, without touching tasks.json or native settings.
            with index():
                saved = configured()
                current = selections(args.profile)
                for role in choices:
                    if any(update.startswith(role+'=') for update in args.set):
                        current[role] = choices[role]
                choices = current
                updated = deepcopy(saved)
                updated['profiles'][args.profile] = choices
                if args.profile == 'normal':
                    updated['profiles']['duo'] = {
                        role: {'model': choices[role]['model'], 'effort': 'xhigh'}
                        for role in ('codex', 'opus')}
                if updated != saved:
                    saved = updated
                    write_json(state_dir()/'models.json', saved)
        if args.rows:
            for role, choice in choices.items():
                allowed = ('xhigh',) if args.profile == 'duo' else EFFORTS[role]
                print('\t'.join((role, choice['model'], choice['effort'], ', '.join(allowed))))
            return
        report = {'profile': args.profile, 'models': choices,
            'configuration': str(state_dir()/'models.json'),
            'configured': args.profile in configured()['profiles'],
            'dependencies': {name: shutil.which(name) for name in sorted({CLI[r] for r in choices})},
            'candidate_verified_on': CATALOG['verified_on'],
            'verification': 'CLI presence and saved choices only; account access, CLI flags, provider effort and live calls unverified.'}
        if args.profile == 'normal':
            report['duo_transport_note'] = ('Saving normal also selects its Codex/Opus model IDs for future Duo tasks, '
                'at the Duo transport\'s required xhigh effort. Existing pairs keep their pinned models.')
        print(json.dumps(report, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
