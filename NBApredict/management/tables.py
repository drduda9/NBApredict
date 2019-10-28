from datetime import datetime
from datatotable.database import Database
from datatotable.data import DataOperator
from nbapredict.scrapers import team_scraper, line_scraper, season_scraper
from nbapredict.configuration import Config
from sqlalchemy import ForeignKey, UniqueConstraint


def create_team_table(db, teams_data, tbl_name):
    columns = teams_data.columns
    columns["team_name"].append({"unique": True})
    db.map_table(tbl_name=tbl_name, column_types=columns)
    db.create_tables()
    db.clear_mappers()


def create_team_stats_table(db, team_stats_data, team_tbl, tbl_name):
    """
    ToDo: Change Unique Constraint to use new format once datatotable update is incorporated
    """
    columns = team_stats_data.columns
    columns['team_id'].append(ForeignKey("{}.id".format(team_tbl.__table__.fullname)))
    constraints = {UniqueConstraint: ["team_id", "scrape_time"]}
    db.map_table(tbl_name=tbl_name, column_types=columns, constraints=constraints)
    db.create_tables()
    db.clear_mappers()

def update_team_stats_table(db, session):
    pass


def values_to_foreign_key(foreign_tbl, foreign_key, foreign_value, child_data):
    """Return values from child data that exist in the foreign_tbl transformed into foreign key values

    Args:
        foreign_tbl: The foreign table mapping child data references
        foreign_key: The name of the column containing foreign key values
        foreign_value: The name of the column containing values to match with child data
        child_data: A list of data with values contained in foreign value

    Returns:
         A list of values from the foreign key column that correspond to child data's relationship to the foreign values
    """
    rows = session.query(getattr(foreign_tbl, foreign_key), getattr(foreign_tbl, foreign_value)).\
        filter(getattr(foreign_tbl, foreign_value).in_(child_data)).all()
    conversion_dict = {getattr(row, foreign_value): getattr(row, foreign_key) for row in rows}
    return [conversion_dict[i] for i in child_data]


def main(db, session):
    year = Config.get_property("league_year")
    team_dict = team_scraper.scrape(database=db)  # ToDo: Reformat team_scraper to not need DB
    teams_data = DataOperator({"team_name": team_dict["team_name"]})


    teams_tbl_name = "teams_{}".format(year)
    if not db.table_exists(teams_tbl_name):
        create_team_table(db=db, teams_data=teams_data, tbl_name=teams_tbl_name)
        teams_tbl = db.table_mappings[teams_tbl_name]
        session.add_all([teams_tbl(**row) for row in teams_data.rows])
        session.commit()
        del teams_tbl

    team_stats_tbl_name = "team_stats_{}".format(year)
    teams_tbl = db.table_mappings[teams_tbl_name]
    team_dict['team_id'] = team_dict.pop('team_name')
    team_dict['team_id'] = values_to_foreign_key(foreign_tbl=teams_tbl, foreign_key="id", foreign_value="team_name",
                                                 child_data=team_dict['team_id'])
    team_stats_data = DataOperator(team_dict)
    if not db.table_exists(team_stats_tbl_name):
        create_team_stats_table(db=db, team_stats_data=team_stats_data, team_tbl=teams_tbl,
                                tbl_name=team_stats_tbl_name)
        team_stats_tbl = db.table_mappings[team_stats_tbl_name]
        session.add_all([team_stats_tbl(**row) for row in team_stats_data.rows])
        session.commit()
    else:
        team_stats_tbl = db.table_mappings[team_stats_tbl_name]
        last_insert_scrape_time = session.query(team_stats_tbl.scrape_time).order_by(team_stats_tbl.scrape_time.desc()).\
            first().scrape_time
        last_insert_date = datetime.date(last_insert_scrape_time)
        current_scrape_date = datetime.date(datetime.now())
        if last_insert_date < current_scrape_date:
            session.add_all([team_stats_tbl(**row) for row in team_stats_data.rows])
            session.commit()


if __name__ == "__main__":
    from sqlalchemy.orm import Session

    db = Database("test", Config.get_property("outputs"))
    session = Session(db.engine)
    main(db, session)
    t = 2