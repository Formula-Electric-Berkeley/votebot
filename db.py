import tinydb
import uuid
from abc import ABC

ELECTIONS_TABLE = "elections"

database = tinydb.TinyDB('db.json', indent=4)


class Model(ABC):
    @classmethod
    def from_dict(cls, mapping: dict):
        return cls(**mapping)

    def to_dict(self):
        mapping = vars(self)
        for k in mapping:
            if isinstance(mapping[k], uuid.UUID):
                mapping[k] = str(mapping[k])
        return mapping

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


class Election(Model):
    def __init__(self, eid: uuid.UUID, electee_uid: str, position: str,
                 threshold_pct: float, allowed_voter_uids: list[str], finished: bool):
        super().__init__()
        self.eid = eid
        self.electee_uid = electee_uid
        self.position = position
        self.threshold_pct = threshold_pct
        self.allowed_voter_uids = allowed_voter_uids
        self.finished = finished


class Vote(Model):
    def __init__(self, uid: str, eid: uuid.UUID, is_yes: bool, confirmation: uuid.UUID):
        self.uid = uid
        self.eid = eid
        self.is_yes = is_yes
        self.confirmation = confirmation

    @classmethod
    def from_dict(cls, mapping: dict):
        if not isinstance(mapping['confirmation'], uuid.UUID):
            mapping['confirmation'] = uuid.UUID(mapping['confirmation'])
        return cls.from_dict(mapping)


def create_election(election: Election) -> None:
    elections = database.table(ELECTIONS_TABLE)
    elections.insert(election.to_dict())
    database.table(get_votes_table_name(election.eid))


def list_open_elections() -> list[Election]:
    elections_table = database.table(ELECTIONS_TABLE)
    return [Election.from_dict(v) for v in elections_table.search(tinydb.Query().finished is False)]


def list_elections() -> list[Election]:
    elections_table = database.table(ELECTIONS_TABLE)
    return [Election.from_dict(v) for v in elections_table.all()]


def add_vote(eid: uuid.UUID, uid: str, is_yes: bool) -> uuid.UUID | None:
    elections_table = database.table(ELECTIONS_TABLE)
    election_matches = elections_table.search(tinydb.Query().eid == eid)
    if len(election_matches) != 1:
        return None
    election = Election.from_dict(election_matches[0])
    if uid not in election.allowed_voter_uids:
        return None

    votes_table = database.table(get_votes_table_name(eid))
    vote_matches = votes_table.search(tinydb.Query().uid == uid)
    if len(vote_matches) != 0:
        return None
    vote = Vote(uid, eid, is_yes, uuid.uuid4())
    votes_table.insert(vote.to_dict())
    return vote.confirmation

def get_votes_table_name(eid: uuid.UUID):
    return f'votes_{eid}'


if __name__ == '__main__':
    raise NotImplementedError('Not an entrypoint')
