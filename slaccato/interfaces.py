
class SlackMethod:
    """
    Base Class of User's command.
    """

    @property
    def execution_words(self):
        """This method should be able to return list(str).

        Returns
            list(str): The keywords to execute the method `response`.
        """
        raise NotImplementedError()

    @property
    def help_text(self):
        """This method should able to return the description, guide for this command.

        Returns:
            (str): Description, guide for this command.
        """
        raise NotImplementedError()

    def response(self, channel, thread_ts, user_command, request_user):
        """This method should be able to return a str response

        Args:
            channel (str): Channel with requested user
            thread_ts (str): Thread requested from user
            user_command (str): Text received from user
            request_user (dict): Requested user.
            
        Returns:
            (str): Target channel
            (str): Target thread or None
            (str|list): Message to send
        """
        raise NotImplementedError()
