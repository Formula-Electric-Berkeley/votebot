import os
import shlex
import uuid

import dotenv
from slack_bolt import App, Ack, Respond, Say
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

import db

dotenv.load_dotenv()

CHANNEL_NAME = os.environ['CHANNEL_NAME']
CHANNEL_ID = os.environ['CHANNEL_ID']
ERR_TEXT = '[voting buttons cannot be rendered - please reload]'

app = App(token=os.environ['SLACK_BOT_TOKEN'])

commands = []


def register_command(name, description):
    commands.append((name, description))
    return app.command(name)


def button_action_id(eid, is_yes):
    return f"{eid}_{'yes' if is_yes else 'no'}"


def gen_election_blocks(election: db.Election, electee: db.User) -> list:
    rts_elements = [
        {
            "type": "text",
            "text": "ELECTION:\n",
            "style": {
                "bold": True
            }
        },
        {
            "type": "text",
            "text": "Do you confirm "
        },
        {
            "type": "user",
            "user_id": electee.uid
        },
        {
            "type": "text",
            "text": f" for the position of {election.position}?\nAllowed voters: "
        }
    ]

    space_rts_element = {
        "type": "text",
        "text": " "
    }
    for uid in election.allowed_voter_uids:
        rts_elements.append({
            "type": "user",
            "user_id": uid
        })
        rts_elements.append(space_rts_element)

    return [
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_section",
                    "elements": rts_elements
                }
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": "Yes"
                    },
                    "style": "primary",
                    "value": "Yes",
                    "action_id": button_action_id(election.eid, True)
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "emoji": True,
                        "text": "No"
                    },
                    "style": "danger",
                    "value": "No",
                    "action_id": button_action_id(election.eid, False)
                }
            ]
        }
    ]


@register_command('/vote-create', 'Create an election')
def create_(ack: Ack, respond: Respond, say: Say, client: WebClient, command: dict, body):
    print(command)
    ack()

    if _incorrect_channel(command, respond):
        return
    args = _parse_args(command)
    if _incorrect_num_args(respond, 4, len(args), lambda e, a: a < e):
        return

    electee = db.User.from_str(args[0])
    allowed_voters = [db.User.from_str(v).uid for v in args[3:]]
    election = db.Election(uuid.uuid4(), electee.uid, args[1], args[2], allowed_voters, True)
    if int(election.threshold_pct) > 100:
        post_ephemeral(client, body, 'Threshold percentage greater than 100')
        return
    elif int(election.threshold_pct) < 1:
        post_ephemeral(client, body, 'Threshold percentage should be 0-100')
        return
    db.create_election(election)

    app.action(button_action_id(str(election.eid), True))(gen_add_vote_handler(election.eid, True))
    app.action(button_action_id(str(election.eid), False))(gen_add_vote_handler(election.eid, False))

    blocks = gen_election_blocks(election, electee)
    say(channel=CHANNEL_NAME, blocks=blocks, text=ERR_TEXT)


def gen_add_vote_handler(eid: uuid.UUID, is_yes: bool):
    def add_vote_handler(ack: Ack, say: Say, client: WebClient, body):
        ack()
        confirmation = db.add_vote(eid, body["user"]["id"], is_yes)
        error_msg = "Error while submitting vote. Please try again if you have not already voted and are an allowed voter."
        success_msg = f"Thank you for voting! Your vote: {'yes' if is_yes else 'no'}. Your confirmation code is {confirmation}"
        msg = error_msg if confirmation is None else success_msg
        post_ephemeral(client, body, msg)
    return add_vote_handler


# @register_command('/vote-help', 'Help with using votebot')
# def help_(ack: Ack, respond: Respond, say: Say, command: dict):
#     ack()
#
#     if _incorrect_channel(command, respond):
#         return
#     args = _parse_args(command)
#     if len(args) not in (0, 1):
#         _incorrect_num_args(respond, '0 or 1', len(args))
#         return
#     if len(args) == 0:
#         args.append(False)
#     send_public = args[0]
#
#     cmds_str = '\n'.join([f'{n}: {d}' for n, d in commands])
#     text = '*shopbot*\n\n' \
#            'A slack bot that manages purchasing / shopping carts.\n\n' \
#            '*All commands:*\n' \
#            f'{cmds_str}\n\n' \
#            '*Quickstart:*\n' \
#            '1. Create a cart.\n' \
#            '2. Add items to the cart.\n' \
#            '3. Buy the cart. Approvers will react to the message to approve the purchase.\n' \
#            '4. Once approved, the cart is cleared. Repeat from the beginning for another cart.\n' \
#            '(note: approvers must be added before they can approve any purchases)\n'
#     say(channel=CHANNEL_NAME, text=text) if send_public else respond(text=text)


def post_ephemeral(client, body, text):
    client.chat_postEphemeral(channel=CHANNEL_ID, user=body["user"]["id"], text=text)


def _incorrect_channel(command, respond) -> bool:
    actual_channel = command['channel_name']
    is_incorrect = actual_channel != CHANNEL_NAME
    if is_incorrect:
        respond(text=f'Incorrect channel. Expected {CHANNEL_NAME}, got {actual_channel}.')
    return is_incorrect


def _incorrect_num_args(respond, expected, actual, op=lambda e, a: e != a):
    is_incorrect = op(expected, actual)
    if is_incorrect:
        respond(text=f'Incorrect number of arguments. Expected {expected}, got {actual}.')
    return is_incorrect


def _parse_args(command):
    text = command['text']
    args = []
    last_split_idx = 0
    in_quotes = False
    for i in range(len(text)):
        if text[i] == "\"":
            in_quotes = not in_quotes
        if text[i] == ' ' and not in_quotes:
            args.append(text[last_split_idx:i])
            i += 1
            last_split_idx = i
    if last_split_idx != len(text) - 1:
        args.append(text[last_split_idx:])
    return [v.replace('\"', '') for v in args]


def init_election_actions():
    pass
    # for election in db.list_open_elections():
    #     app.action(button_action_id(election.eid, True))(gen_add_vote_handler(election.eid, True))
    #     app.action(button_action_id(election.eid, False))(gen_add_vote_handler(election.eid, False))

if __name__ == '__main__':
    init_election_actions()
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
