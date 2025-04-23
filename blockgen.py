from abc import ABC, abstractmethod
import models
import random
import string


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


class GenRTSectionLink(GenRTSection):
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url

    def generate(self) -> dict:
        return {
            "type": "link",
            "text": self.text,
            "url": self.url
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
        > **ELECTION:**
        > Do you confirm [ELECTEE] for the position of [POSITION]?
        > Allowed voters: [ALLOWED_VOTERS...]
        > __Election ID: [ELECTION_ID]
        > [YES_BUTTON] [NO_BUTTON]

    :param election_: the election to announce
    :return: the resulting Slack API compliant blocks
    """
    rt_sections = [
        GenRTSectionText('ELECTION:\r\n', bold=True),
        GenRTSectionText('Do you confirm '),
        GenRTSectionUser(election_.electee_uid),
        GenRTSectionText(f' for the position of {election_.position}?\r\nAllowed voters: '),
    ]
    rt_sections.extend(_rts_users(election_))
    rt_sections.append(GenRTSectionText(f'\r\nElection ID: {election_.eid}', italic=True))
    buttons = [
        GenActionButton('Yes', button_action_id(election_.eid, True), False),
        GenActionButton('No', button_action_id(election_.eid, False), True)
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
        >
        > CC all allowed voters: [ALLOWED_VOTERS...]

    :param result: the input election result to format into blocks
    :return: the resulting Slack API compliant blocks
    """
    num_voters = len(result.election.allowed_voter_uids)
    threshold_pct = int(result.election.threshold_pct)
    vote_pct = int(100 * result.num_yes / (result.num_no + result.num_yes))
    threshold_voters = max(1, int(threshold_pct / 100 * num_voters))

    rt_sections = [
        GenRTSectionText('The election of '),
        GenRTSectionUser(result.election.electee_uid),
        GenRTSectionText(f' for {result.election.position} has concluded!\r\nThe final vote '),
        GenRTSectionText('PASSED' if result.is_passed else 'FAILED', bold=True),
        GenRTSectionText(f' with a vote of {result.num_yes} yes to {result.num_no} no ({vote_pct}%).\r\n'
                         f'The threshold for this election was {threshold_pct}% of {num_voters} '
                         f'allowed voters ({threshold_voters})\r\n\r\nCC all allowed voters: '),
    ]
    rt_sections.extend(_rts_users(result.election))
    return [GenRT(rt_sections).generate()]


def vote_confirmation(election_: models.Election, vote: models.Vote) -> list[dict]:
    rt_sections = [
        GenRTSectionText('Thank you for voting in the election of '),
        GenRTSectionUser(election_.electee_uid),
        GenRTSectionText(f' for {election_.position}.\r\nYour vote: '),
        GenRTSectionText('yes' if vote.is_yes else 'no', bold=True),
        GenRTSectionText(f'\r\nYour confirmation code: {vote.confirmation}')
    ]
    return [GenRT(rt_sections).generate()]


def url_forward(url: str) -> list[dict]:
    return [GenRT([GenRTSectionLink('An election you are allowed to vote in has concluded', url)]).generate()]

def button_action_id(eid: str, is_yes: bool) -> str:
    return f'{eid}_{"yes" if is_yes else "no"}'


def random_id(length: int = 8) -> str:
    return ''.join(random.choices(string.digits + string.ascii_letters, k=length))
