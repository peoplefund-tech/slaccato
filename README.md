# Slaccato

> Struectured Slack bot framework

## Installation

```shell
$ pip install slaccato
```

## Example

```python
from slaccato.core import SlackBot, SlackMethod

# Write a new method
class TestMethod(SlackMethod):
    @property
    def execution_words(self):
        return ['테스트', 'test', 'ping']

    @property
    def help_text(self):
        return '*{}*: You can test me!'.format('/'.join(self.execution_words))

    def response(self, channel, user_command, request_user):
        response = 'Oh, {}! here I am!!!'.format(request_user)
        return channel, response
    
slack_bot = SlackBot(slack_bot_token='SLACK_BOT_TOKEN',
                     slack_bot_name='SLACK_BOT_NAME')

slack_bot.add_method(TestMethod)
slack_bot.run()
```

![Test screenshot](./screenshots/screenshot-1.png)
