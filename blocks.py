import models

def button_action_id(eid, is_yes):
    return f"{eid}_{'yes' if is_yes else 'no'}"


def gen_election_blocks(election: models.Election, electee: models.User) -> list:
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

    rts_elements.append({
        "type": "text",
        "text": f"\nElection ID: {election.eid}",
        "style": {
            "italic": True
        }
    })

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


def gen_election_result_blocks(result: models.ElectionResult) -> str:
    num_voters = len(result.election.allowed_voter_uids)
    threshold_pct = int(result.election.threshold_pct)
    vote_pct = int(100 * result.num_yes / (result.num_no + result.num_yes))
    # TODO add more information and format into rich text blocks (like above)
    return (f'The election for {result.election.position} has concluded! The final vote {"PASSED" if result.is_passed else "FAILED"} '
            f'with a vote of {result.num_yes} yes to {result.num_no} no ({vote_pct}%). '
            f'The threshold for this election was {threshold_pct}% of {num_voters} allowed voters ({int(threshold_pct / 100 * num_voters)})')