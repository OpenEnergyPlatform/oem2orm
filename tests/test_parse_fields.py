# from oem2orm.oep_oedialect_oem2orm import (
#     setup_db_connection,
#     collect_tables_from_oem_object,
#     create_tables,
#     api_updateMdOnTable,
# )

# from oemetadata.v2.v20.example import OEMETADATA_V20_EXAMPLE


# def test_create_tables(
#     oep_url="localhost:8000",
#     api_token="4fd4be1e8c0478e0f0921bd58c7fcada9ff2e2a1",
#     user="test",
# ):
#     """
#     Only works with running OEP instance available at <URL>. Use the parameter
#     oep_url to specify on which instance tests will run. Use the parameter api_token
#     for authentication with the specific instance.

#     """
#     db_conn = setup_db_connection(host=oep_url, token=api_token, user=user)

#     sa_tables = collect_tables_from_oem_object(db=db_conn, oems=[OEMETADATA_V20_EXAMPLE])
#     create_tables(db=db_conn, tables=sa_tables)


# if __name__ == "__main__":
#     test_create_tables()
