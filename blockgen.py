from abc import ABC, abstractmethod
import models

import util


class GenBase(ABC):
    @abstractmethod
    def generate(self) -> dict:
        raise NotImplementedError('generate() must be implemented by subclasses')


class GenAction(GenBase, ABC):
    pass


class GenActionButton(GenAction):
    def __init__(self, text: str, action_id: str, is_red: bool = False):
        self.text = text
        self.action_id = action_id
        self.is_red = is_red

    def generate(self) -> dict:
        return {
            'type': 'button',
            'text': {
                'type': 'plain_text',
                'emoji': True,
                'text': self.text
            },
            'style': 'danger' if self.is_red else 'primary',
            'value': self.text,
            'action_id': self.action_id
        }


class GenActions(GenBase):
    def __init__(self, actions: list[GenAction]):
        self.actions = actions

    def generate(self) -> dict:
        return {
            'type': 'actions',
            'elements': [a.generate() for a in self.actions]
        }


class GenRTSection(GenBase, ABC):
    pass


class GenRTSectionUser(GenRTSection):
    def __init__(self, uid: str):
        self.uid = uid

    def generate(self) -> dict:
        return {
            'type': 'user',
            'user_id': self.uid
        }


class GenRTSectionText(GenRTSection):
    def __init__(self, text: str, bold: bool = False, italic: bool = False):
        self.text = text
        self.bold = bold
        self.italic = italic

    def generate(self) -> dict:
        return {
            'type': 'text',
            'text': self.text,
            'style': {
                'bold': self.bold,
                'italic': self.italic
            }
        }


class GenRT(GenBase):
    def __init__(self, elements: list[GenRTSection]):
        self.elements = elements

    def generate(self) -> dict:
        return {
            'type': 'rich_text',
            'elements': [
                {
                    'type': 'rich_text_section',
                    'elements': [e.generate() for e in self.elements]
                }
            ]
        }


_SPACE_RTS_ELEMENT = GenRTSectionText(' ')


def _rts_users(election_: models.Election) -> list[GenRTSection]:
    rt_sections = []
    for uid in election_.allowed_voter_uids:
        rt_sections.append(GenRTSectionUser(uid))
        rt_sections.append(_SPACE_RTS_ELEMENT)
    return rt_sections


def election(election_: models.Election) -> list[dict]:
    """
    Generate Slack API blocks for the announcement of a single election

    Message displayed:
        > **ELECTION**
        > Do you confirm [ELECTEE] for the position of [POSITION]?
        > Allowed voters: [ALLOWED_VOTERS...]
        > __Election ID: [ELECTION_ID]__
        > [YES_BUTTON] [NO_BUTTON]

    :param election_: the election to announce
    :return: the resulting Slack API compliant blocks
    """
    rt_sections = [
        GenRTSectionText('ELECTION\r\n', bold=True),
        GenRTSectionText('Do you confirm '),
        GenRTSectionUser(election_.electee_uid),
        GenRTSectionText(f' for the position of {election_.position}?\r\nAllowed voters: '),
    ]
    rt_sections.extend(_rts_users(election_))
    rt_sections.append(GenRTSectionText(f'\r\nElection ID: {election_.eid}', italic=True))
    buttons = [
        GenActionButton('Yes', util.button_action_id(election_.eid, True), False),
        GenActionButton('No', util.button_action_id(election_.eid, False), True)
    ]
    return [
        GenRT(rt_sections).generate(),
        GenActions(buttons).generate()
    ]


def election_result(result: models.ElectionResult) -> list[dict]:
    """
    Generate Slack API blocks for the result of a single election.

    Message displayed:
        > The election of [ELECTEE] for [POSITION] has concluded!
        > The final vote **[PASSED/FAILED]** with a vote of [NUM_YES] yes to [NUM_NO] no ([VOTE_PCT]%).
        > The threshold for this election was [THRESHOLD_PCT]% of [NUM_VOTERS] allowed voters [THRESHOLD_VOTERS].
        > Reporting percentage was [REPORTING_PCT] ([REPORTING_VOTERS]/[NUM_VOTERS]).
        > __Election ID: [ELECTION_ID]__

    :param result: the input election result to format into blocks
    :return: the resulting Slack API compliant blocks
    """
    threshold_pct = int(result.election.threshold_pct)
    threshold_voters = max(1, int(threshold_pct / 100 * result.num_voters))
    rt_sections = [
        GenRTSectionText('ELECTION RESULT\r\n', bold=True),
        GenRTSectionText('The election of '),
        GenRTSectionUser(result.election.electee_uid),
        GenRTSectionText(f' for {result.election.position} has concluded!\r\nThe final vote '),
        GenRTSectionText('PASSED' if result.is_passed else 'FAILED', bold=True),
        GenRTSectionText(f' with a vote of {result.num_yes} yes to {result.num_no} no ({result.vote_pct}%).\r\n'
                         f'The threshold for this election was {threshold_pct}% of {result.num_voters} '
                         f'allowed voters ({threshold_voters}).\r\nReporting percentage was {result.reporting_pct}% '
                         f'({result.reporting_voters}/{result.num_voters}).\r\n'),
        GenRTSectionText(f'Election ID: {result.election.eid}', italic=True)
    ]
    return [GenRT(rt_sections).generate()]


def vote_confirmation(election_: models.Election, vote: models.Vote) -> list[dict]:
    """
    Generate Slack API blocks for the confirmation of a vote.

    Message displayed:
        > Thank you for voting in the election of [ELECTEE] for [POSITION].
        > Your vote: **[VOTE]**
        > Your confirmation code: [CONFIRMATION_CODE]
        > __Election ID: [ELECTION_ID]__

    :param election_: the Election that was voted in
    :param vote: the Vote that was submitted to the passed Election
    :return: the resulting Slack API compliant blocks
    """
    rt_sections = [
        GenRTSectionText('Thank you for voting in the election of '),
        GenRTSectionUser(election_.electee_uid),
        GenRTSectionText(f' for {election_.position}.\r\nYour vote: '),
        GenRTSectionText('yes' if vote.is_yes else 'no', bold=True),
        GenRTSectionText(f'\r\nYour confirmation code: {vote.confirmation}\r\n'),
        GenRTSectionText(f'Election ID: {election_.eid}', italic=True)
    ]
    return [GenRT(rt_sections).generate()]
