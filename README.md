![Deviant Database Service Logo](deviant_db_service_logo.png)

# Deviant DBS

Deviant Database Service also known as Deviant DBS is a service independent of DeviantCord that is responsible for interacitng with the DeviantArt API for the purpose of fetching information on DeviantArt users, galleries, and other resources to properly inform DeviantCord users when a new deviation is posted. 

DeviantDBS has been a staple of DeviantCord since DeviantCord 3, and has been updated to its shiny new V2.0.0 version that refactors the codebase to be more readable and integrates with DeviantCord's new notification system powered by RabbitMQ.

DeviantDBS is written in Python and relies on three different services to operate: Redis/Valkey, RabbitMQ, and a PostgreSQL database.

## Redis/Valkey

DeviantDBS uses Redis/Valkey as its database layer. This allows DeviantDBS to cache data in memory so that it can be retrieved very quickly. This is especially useful for data that is requested multiple times, such as user information or gallery information.

## RabbitMQ

DeviantDBS uses RabbitMQ to send notifications to DeviantCord when a new deviation is posted. This allows DeviantCord to notify users in real-time when a new deviation is posted, without the need to manually refresh the page.

## PostgreSQL

DeviantDBS uses PostgreSQL as its primary database. This allows DeviantDBS to store data on a more permanent basis, such as user information or gallery information.

## System Requirements

- Python 3.10+
- Redis/Valkey 6+
- RabbitMQ 3.12+
- PostgreSQL 15+ Recommended

## Tested Versions
- Python 3.12
- Redis/Valkey 7.2
- RabbitMQ 4.0
- PostgreSQL 16

## Can I Contribute?
Yes! We are always looking for contributors to help us improve Deviant DBS. Please visit the DeviantCord Github repository and follow the contributing section in that repository's readme here: [DeviantCord Github](https://github.com/DeviantCord/DeviantCord)

## License
Deviant DBS is licensed under the [GNU Affero General Public License v3.0](https://github.com/DeviantCord/DeviantCord/blob/master/LICENSE)

## Documentation for Self Hosting
Currently there is no documentation for self hosting Deviant DBS. This is a work in progress.

## Credits
- [@deviantart](https://github.com/DeviantArt) for developing the DeviantArt and Sta.sh API
- [@haloman30](https://github.com/haloman30) for creating the DeviantCord logo and Deviant DBS logo. 
- [@ErriteEpticRikez](https://github.com/ErriteEpticRikez) for investigating DA's API, creating functionality for it in Python, and overall developing the bot
- [@mosquito](https://github.com/mosquito) for developing/creating aio_pika, a Python library for RabbitMQ that is used by Deviant DBS.
- [aio_pika Contributors](https://github.com/mosquito/aio-pika/blob/master/docs/source/index.rst#thanks-for-contributing) for developing aio_pika
- [Redis Inc](https://redis.io) for developing Redis and the Python Redis library we use
- [Danielle Varrazzo](https://github.com/dvarrazzo) for developing Psycopg2, the PostgreSQL Python library we use
- [Sentry.io Team](https://sentry.io) for providing error monitoring for Deviant DBS
- [RabbitMQ Team](https://www.rabbitmq.com) for developing RabbitMQ
