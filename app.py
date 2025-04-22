import os
import uuid

import dotenv
from slack_bolt import App, Ack, Respond, Say
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

import blockgen
import db
import models

dotenv.load_dotenv()

CHANNEL_NAME = os.environ['CHANNEL_NAME']
CHANNEL_ID = os.environ['CHANNEL_ID']

ERR_VOTE_RENDER = '[voting buttons cannot be rendered - please reload]'
ERR_NON_ALLOWED_VOTER = 'ERROR: Vote not submitted. You are not an allowed voted.'
ERR_USER_ALREADY_VOTED = 'ERROR: Vote not submitted. You have already voted.'
ERR_ELECTION_FINISHED = 'ERROR: Vote not submitted. This election has finished.'

app = App(token=os.environ['SLACK_BOT_TOKEN'])

commands = []


def register_command(name, description):
    commands.append((name, description))
    return app.command(name)


def init_election_actions():
    for election in db.list_open_elections():
        app.action(blockgen.button_action_id(str(election.eid), True))(gen_add_vote_handler(election.eid, True))
        app.action(blockgen.button_action_id(str(election.eid), False))(gen_add_vote_handler(election.eid, False))


@register_command('/vote-create', 'Create an election')
def create_(ack: Ack, respond: Respond, say: Say, client: WebClient, command: dict, body):
    print(command)
    ack()

    if _incorrect_channel(command, respond):
        return
    args = _parse_args(command)
    if _incorrect_num_args(respond, 4, len(args), lambda e, a: a < e):
        return

    electee = models.User.from_str(args[0])

    allowed_voters = []
    for voter_escstr in args[3:]:
        if voter_escstr.startswith('<!subteam^'):
            ug = models.UserGroup.from_str(voter_escstr)
            ug_users = client.usergroups_users_list(usergroup=ug.ugid)
            allowed_voters.extend(ug_users['users'])
        else:
            allowed_voters.append(models.User.from_str(voter_escstr).uid)

    election = models.Election(uuid.uuid4(), electee.uid, args[1], args[2], allowed_voters, False)
    if int(election.threshold_pct) > 100:
        post_ephemeral(client, body, 'Threshold percentage greater than 100')
        return
    elif int(election.threshold_pct) < 1:
        post_ephemeral(client, body, 'Threshold percentage should be 0-100')
        return
    db.create_election(election)

    app.action(blockgen.button_action_id(str(election.eid), True))(gen_add_vote_handler(election.eid, True))
    app.action(blockgen.button_action_id(str(election.eid), False))(gen_add_vote_handler(election.eid, False))

    say(channel=CHANNEL_NAME, blocks=blockgen.election(election), text=ERR_VOTE_RENDER)


def gen_add_vote_handler(eid: uuid.UUID, is_yes: bool):
    def add_vote_handler(ack: Ack, say: Say, client: WebClient, body):
        ack()

        uid = body['user']['id']
        if db.get_election_result(eid).is_finished:
            post_ephemeral(client, body, ERR_ELECTION_FINISHED)
            return
        elif not db.is_user_allowed_voter(eid, uid):
            post_ephemeral(client, body, ERR_NON_ALLOWED_VOTER)
            return
        elif db.has_user_voted(eid, uid):
            post_ephemeral(client, body, ERR_USER_ALREADY_VOTED)
            return

        vote = db.add_vote(eid, uid, is_yes)
        result = db.get_election_result(eid)
        send_dm(client, [uid], blocks=blockgen.vote_confirmation(result.election, vote))

        if result.is_finished:
            db.mark_election_finished(result.election)
            # TODO allowed voters should either be forwarded this or replied in thread
            say(channel=CHANNEL_NAME, blocks=blockgen.election_result(result))

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
    client.chat_postEphemeral(channel=CHANNEL_ID, user=body['user']['id'], text=text)


def send_dm(client: WebClient, uids: list[str], text=None, blocks=None) -> None:
    dm_channel_resp = client.conversations_open(users=uids)
    dm_channel_id = dm_channel_resp['channel']['id']
    if text is not None:
        client.chat_postMessage(channel=dm_channel_id, text=text)
    elif blocks is not None:
        client.chat_postMessage(channel=dm_channel_id, blocks=blocks)
    else:
        raise ValueError('Neither text nor blocks provided for DM')


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
        if text[i] == '\"':
            in_quotes = not in_quotes
        if text[i] == ' ' and not in_quotes:
            args.append(text[last_split_idx:i])
            i += 1
            last_split_idx = i
    if last_split_idx != len(text) - 1:
        args.append(text[last_split_idx:])
    return [v.replace('\"', '') for v in args]


if __name__ == '__main__':
    init_election_actions()
    SocketModeHandler(app, os.environ['SLACK_APP_TOKEN']).start()
