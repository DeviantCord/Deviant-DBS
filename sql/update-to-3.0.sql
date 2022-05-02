create table deviantcord.deviant_accounts
(
	username text,
	password text
);

alter table deviantcord.deviation_data
	add shard_id int;

alter table deviantcord.deviation_data_all
	add shard_id int;

alter table deviantcord.deviation_listeners
	add shard_id int;
