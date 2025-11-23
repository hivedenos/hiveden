import click

class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop("mutually_exclusive", []))
        help = kwargs.get("help", "")
        if self.mutually_exclusive:
            ex_str = ", ".join(self.mutually_exclusive)
            kwargs["help"] = help + (
                " NOTE: This option is mutually exclusive with "
                " options: [%s]." % ex_str
            )
        super(MutuallyExclusiveOption, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                "Illegal usage: `%s` is mutually exclusive with "
                " `%s`." % (self.name, ", ".join(self.mutually_exclusive))
            )

        return super(MutuallyExclusiveOption, self).handle_parse_result(ctx, opts, args)
