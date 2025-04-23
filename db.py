import tinydb

import models
import util


ELECTIONS_TABLE = "elections"

database = tinydb.TinyDB('db.json', indent=4)


def create_election(election: models.Election) -> None:
    elections = database.table(ELECTIONS_TABLE)
    elections.insert(election.to_dict())
    database.table(get_votes_table_name(election.eid))

def get_election_result(eid: str, requestor_uid: str = None) -> models.ElectionResult:
    elections_table = database.table(ELECTIONS_TABLE)
    election_matches = elections_table.search(tinydb.Query().eid == eid)
    if len(election_matches) != 1:
        return models.ShortCircuitElectionResult()
    election = models.Election.from_dict(election_matches[0])
    if requestor_uid is not None:
        if requestor_uid != election.creator_uid:
            return models.InvalidPermissionsElectionResult()
    elif election.finished:
        # Return immediately if election was previously finished
        # Do not immediately return if checking vote (requestor UID passed)
        return models.ShortCircuitElectionResult()

    # If election not previously finished, calculate if it is now
    votes_table = database.table(get_votes_table_name(eid))
    vote_matches = votes_table.search(tinydb.Query().eid == eid)
    num_yes = 0
    num_no = 0
    for m in vote_matches:
        v = models.Vote.from_dict(m)
        if v.is_yes:
            num_yes += 1
        else:
            num_no += 1
    return models.ElectionResult(election, num_yes, num_no)


def mark_election_finished(election: models.Election) -> None:
    election.finished = True
    elections = database.table(ELECTIONS_TABLE)
    elections.upsert(election.to_dict(), tinydb.Query().eid == election.eid)
    database.table(get_votes_table_name(election.eid))

def list_open_elections() -> list[models.Election]:
    elections_table = database.table(ELECTIONS_TABLE)
    return [models.Election.from_dict(v) for v in elections_table.search(tinydb.Query().finished == False)]


def list_elections() -> list[models.Election]:
    elections_table = database.table(ELECTIONS_TABLE)
    return [models.Election.from_dict(v) for v in elections_table.all()]


def is_user_allowed_voter(eid: str, uid: str) -> bool:
    elections_table = database.table(ELECTIONS_TABLE)
    election_matches = elections_table.search(tinydb.Query().eid == eid)
    if len(election_matches) != 1:
        return False
    election = models.Election.from_dict(election_matches[0])
    if uid not in election.allowed_voter_uids:
        return False
    return True


def has_user_voted(eid: str, uid: str) -> bool:
    votes_table = database.table(get_votes_table_name(eid))
    vote_matches = votes_table.search(tinydb.Query().uid == uid)
    return len(vote_matches) != 0


def add_vote(eid: str, uid: str, is_yes: bool) -> models.Vote:
    votes_table = database.table(get_votes_table_name(eid))
    vote = models.Vote(uid, eid, is_yes, util.random_id())
    votes_table.insert(vote.to_dict())
    return vote


def is_vote_valid(eid: str, confirmation: str) -> bool:
    votes_table = database.table(get_votes_table_name(eid))
    matches = votes_table.search(tinydb.Query().confirmation == confirmation and tinydb.Query().eid == eid)
    return len(matches) == 1


def get_votes_table_name(eid: str):
    return f'votes_{eid}'


if __name__ == '__main__':
    raise NotImplementedError('Not an entrypoint')
