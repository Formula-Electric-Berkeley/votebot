from abc import ABC

import util


class Model(ABC):
    @classmethod
    def from_dict(cls, mapping: dict):
        return cls(**mapping)

    def to_dict(self):
        return vars(self)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.to_dict() == other.to_dict()

    def __str__(self):
        attributes = ", ".join(f"{k}={v}" for k, v in self.to_dict().items())
        return f'{self.__class__.__name__}({attributes})'

    def __repr__(self):
        return self.__str__()


class User(Model):
    def __init__(self, name: str, uid: str):
        super().__init__()
        self.name = name
        self.uid = uid

    @classmethod
    def from_str(cls, escaped_str: str):
        parts = escaped_str[2:-1].split('|')
        return cls(name=parts[1], uid=parts[0])

    def mention(self) -> str:
        return f'<@{self.name}>'


class UserGroup(Model):
    def __init__(self, name: str, ugid: str):
        super().__init__()
        self.name = name
        self.ugid = ugid

    @classmethod
    def from_str(cls, escaped_str: str):
        parts = escaped_str.removeprefix('<!subteam^')[:-1].split("|@")
        return cls(name=parts[1], ugid=parts[0])

    def mention(self) -> str:
        return f'<!subteam^{self.ugid}|@{self.name}>'


class Election(Model):
    def __init__(self, eid: str, electee_uid: str, position: str, threshold_pct: float,
                 allowed_voter_uids: list[str], creator_uid: str, finished: bool):
        super().__init__()
        self.eid = eid
        self.electee_uid = electee_uid
        self.position = position
        self.threshold_pct = threshold_pct
        self.allowed_voter_uids = allowed_voter_uids
        self.creator_uid = creator_uid
        self.finished = finished


class Vote(Model):
    def __init__(self, uid: str, eid: str, is_yes: bool, confirmation: str):
        super().__init__()
        self.uid = uid
        self.eid = eid
        self.is_yes = is_yes
        self.confirmation = confirmation


class ElectionResult:
    def __init__(self, election: Election, num_yes: int, num_no: int):
        self.election = election
        self.num_yes = num_yes
        self.num_no = num_no

        self.num_voters = len(election.allowed_voter_uids)
        self.reporting_voters = num_no + num_yes
        self.vote_pct = 0 if self.reporting_voters == 0 else int(100 * num_yes / self.reporting_voters)
        self.reporting_pct = 0 if self.num_voters == 0 else int(100 * self.reporting_voters / self.num_voters)

        # Always round number of yes required DOWN (floor)
        yes_to_pass = max(1, int((int(self.election.threshold_pct) / 100) * self.num_voters))
        no_to_fail = max(0, self.num_voters - yes_to_pass)
        # Must EXCEED number of no, but must MEET number of yes
        self.is_finished = self.num_yes >= yes_to_pass or self.num_no > no_to_fail
        self.is_passed = num_yes >= yes_to_pass and self.num_no <= no_to_fail


BLANK_ELECTION = Election(util.random_id(), str(), str(), float(), list(), str(), True)


class ShortCircuitElectionResult(ElectionResult):
    def __init__(self):
        super().__init__(BLANK_ELECTION, 0, 0)


class InvalidPermissionsElectionResult(ElectionResult):
    def __init__(self):
        super().__init__(BLANK_ELECTION, 0, 0)
