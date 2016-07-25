# pokebot
Pokemon Go slackbot

# config.json

Copy `config.json.default` to `config.json`.

* `prod_channel`: the Slack channel that alerts for Pokemon within 1 block go to
* `test_channel`: the Slack channel that all other alerts go to
* `webhook_url`: Slack webhook
* `office`: location of the office
* `authentication`
  * `auth_service`: either `"ptc"` for Pokemon Trainer Club or `"google"` for Google
  * `username`
  * `password`

