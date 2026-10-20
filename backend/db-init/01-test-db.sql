-- Runs once when the Postgres volume is first created.
-- A separate database for the automated tests so they never touch real data.
CREATE DATABASE voiceid_test OWNER voiceid;
