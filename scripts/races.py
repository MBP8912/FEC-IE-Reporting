"""FEC verified IDs for independent expenditure dashboards, 2026 general election.

Two chart slots preserve the tested NY-17 schema: internal lawler=Republican,
conley=Democrat/DFL. Human-facing text always uses the per-race candidate names.
Official candidate profiles: https://www.fec.gov/data/candidate/<candidate_id>/
"""
RACES = {
  "NY-17": {
    "state": "NY",
    "district": "17",
    "republican": {
      "name": "Mike Lawler",
      "short": "Lawler",
      "id": "H2NY17162",
      "surname": "lawler"
    },
    "democratic": {
      "name": "Cait Conley",
      "short": "Conley",
      "id": "H6NY17171",
      "surname": "conley"
    }
  },
  "CO-4": {
    "state": "CO",
    "district": "04",
    "republican": {
      "name": "Lauren Boebert",
      "short": "Boebert",
      "id": "H0CO03165",
      "surname": "boebert"
    },
    "democratic": {
      "name": "Eileen Laubacher",
      "short": "Laubacher",
      "id": "H6CO04202",
      "surname": "laubacher"
    }
  },
  "CO-5": {
    "state": "CO",
    "district": "05",
    "republican": {
      "name": "Jeff Crank",
      "short": "Crank",
      "id": "H6CO05142",
      "surname": "crank"
    },
    "democratic": {
      "name": "Jessica Killin",
      "short": "Killin",
      "id": "H6CO05324",
      "surname": "killin"
    }
  },
  "IA-1": {
    "state": "IA",
    "district": "01",
    "republican": {
      "name": "Mariannette Miller-Meeks",
      "short": "Miller-Meeks",
      "id": "H8IA02043",
      "surname": "miller meeks"
    },
    "democratic": {
      "name": "Christina Bohannan",
      "short": "Bohannan",
      "id": "H2IA02111",
      "surname": "bohannan"
    }
  },
  "MN-1": {
    "state": "MN",
    "district": "01",
    "republican": {
      "name": "Brad Finstad",
      "short": "Finstad",
      "id": "H2MN01223",
      "surname": "finstad"
    },
    "democratic": {
      "name": "Jake Johnson",
      "short": "Johnson",
      "id": "H6MN01190",
      "surname": "johnson",
      "given": "jacob"
    }
  },
  "NE-2": {
    "state": "NE",
    "district": "02",
    "republican": {
      "name": "Brinker Harding",
      "short": "Harding",
      "id": "H6NE02208",
      "surname": "harding"
    },
    "democratic": {
      "name": "Denise Powell",
      "short": "Powell",
      "id": "H6NE02174",
      "surname": "powell"
    }
  },
  "WI-1": {
    "state": "WI",
    "district": "01",
    "republican": {
      "name": "Bryan Steil",
      "short": "Steil",
      "id": "H8WI01156",
      "surname": "steil"
    },
    "democratic": {
      "name": "Mitchell Berman",
      "short": "Berman",
      "id": "H6WI01283",
      "surname": "berman"
    }
  },
  "NY-19": {
    "state": "NY",
    "district": "19",
    "republican": {
      "name": "Peter Oberacker",
      "short": "Oberacker",
      "id": "H6NY19268",
      "surname": "oberacker"
    },
    "democratic": {
      "name": "Josh Riley",
      "short": "Riley",
      "id": "H8NY22177",
      "surname": "riley"
    }
  },
  "CA-13": {
    "state": "CA",
    "district": "13",
    "republican": {
      "name": "Kevin Lincoln",
      "short": "Lincoln",
      "id": "H4CA09093",
      "surname": "lincoln"
    },
    "democratic": {
      "name": "Adam Gray",
      "short": "Gray",
      "id": "H2CA13115",
      "surname": "gray"
    }
  }
}
RACE_CODES = list(RACES)
ALL_CANDIDATE_IDS = [v["id"] for race in RACES.values() for v in (race["republican"],race["democratic"])]
assert len(RACE_CODES) == 9 and len(ALL_CANDIDATE_IDS) == len(set(ALL_CANDIDATE_IDS)) == 18
