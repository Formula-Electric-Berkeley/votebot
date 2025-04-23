import os

import dotenv
from slack_bolt import App, Ack, Respond, Say
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.web import SlackResponse

import blockgen
import db
import models

dotenv.load_dotenv()

CHANNEL_NAME = os.environ['CHANNEL_NAME']
CHANNEL_ID = os.environ['CHANNEL_ID']

ERR_VOTE_RENDER = '[voting buttons cannot be rendered - please reload]'
ERR_DM_RENDER = '[this DM was not sent correctly - please try again]'
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
        app.action(blockgen.button_action_id(election.eid, True))(gen_add_vote_handler(election.eid, True))
        app.action(blockgen.button_action_id(election.eid, False))(gen_add_vote_handler(election.eid, False))


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

    election = models.Election(blockgen.random_id(), electee.uid, args[1], args[2], allowed_voters, False)
    if int(election.threshold_pct) > 100:
        post_ephemeral(client, body, 'Threshold percentage greater than 100')
        return
    elif int(election.threshold_pct) < 1:
        post_ephemeral(client, body, 'Threshold percentage should be 0-100')
        return
    db.create_election(election)

    app.action(blockgen.button_action_id(election.eid, True))(gen_add_vote_handler(election.eid, True))
    app.action(blockgen.button_action_id(election.eid, False))(gen_add_vote_handler(election.eid, False))

    say(channel=CHANNEL_NAME, blocks=blockgen.election(election), text=ERR_VOTE_RENDER)


def gen_add_vote_handler(eid: str, is_yes: bool):
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
            announcement = say(channel=CHANNEL_NAME, blocks=blockgen.election_result(result))
            announcement_url = client.chat_getPermalink(channel=CHANNEL_ID, message_ts=announcement['ts'])
            for voter_uid in result.election.allowed_voter_uids:
                # Send SEPARATE DMs to each allowed voter instead of one group DM
                send_dm(client, [voter_uid], blocks=blockgen.url_forward(announcement_url['permalink']))

    return add_vote_handler


@register_command('/vote-confirm', 'Confirm a vote was counted')
def confirm_(ack: Ack, respond: Respond, command: dict):
    print(command)
    ack()

    if _incorrect_channel(command, respond):
        return
    args = _parse_args(command)
    if _incorrect_num_args(respond, 2, len(args)):
        return
    eid, confirmation = args

    if db.is_vote_valid(eid, confirmation):
        respond(text='This vote is valid!')
    else:
        respond(text='This vote is invalid. If you believe this to be in error, '
                     'confirm your confirmation and election ID, or try voting again.')


# @register_command('/vote-check', 'Check the current results of an election')
# def check_(ack: Ack, respond: Respond, command: dict):
#     print(command)
#     ack()
#
#     if _incorrect_channel(command, respond):
#         return
#     args = _parse_args(command)
#     if _incorrect_num_args(respond, 2, len(args)):
#         return
#     eid, confirmation = args
#


@register_command('/vote-help', 'Help with using votebot')
def help_(ack: Ack, respond: Respond, command: dict):
    ack()

    if _incorrect_channel(command, respond):
        return
    args = _parse_args(command)
    if _incorrect_num_args(respond, 0, len(args)):
        return

    cmds_str = '\n'.join([f'{n}: {d}' for n, d in commands])
    text = '*votebot*\n\n' \
           'A slack bot that manages elections.\n\n' \
           '*All commands:*\n' \
           f'{cmds_str}\n\n' \
           '*Quickstart:*\n' \
           '1. Create an election (/vote-create).\n' \
           '2. Allowed voters click one of the voting buttons in the created message.\n' \
           '3. Voters will get a DM confirming their vote, and can re-confirm at any time (/vote-confirm). \n' \
           '4. Once the election has finished, a message will be send by votebot with the final vote.\n' \
           'The creator of the election may check the vote count at any time (/vote-check). \n'
    respond(text=text)


def post_ephemeral(client, body, text):
    client.chat_postEphemeral(channel=CHANNEL_ID, user=body['user']['id'], text=text)


def send_dm(client: WebClient, uids: list[str], text=None, blocks=None) -> SlackResponse:
    dm_channel_resp = client.conversations_open(users=uids)
    dm_channel_id = dm_channel_resp['channel']['id']
    if text is not None:
        return client.chat_postMessage(channel=dm_channel_id, text=text, unfurl_links=True)
    elif blocks is not None:
        return client.chat_postMessage(channel=dm_channel_id, blocks=blocks, text=ERR_DM_RENDER, unfurl_links=True)
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
