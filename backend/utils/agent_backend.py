from deepagents.backends.local_shell import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse


EMPTY_OUTPUT_MESSAGE = (
    "Command succeeded with no stdout/stderr. This is not an error.\n"
    "If the command wrote files, inspect them with `glob` or `read_file`.\n"
    "If terminal output is required, rerun once with explicit `print(...)` "
    "or `Write-Output`."
)


class FriendlyLocalShellBackend(LocalShellBackend):
    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        result = super().execute(command, timeout=timeout)
        return self._normalize_empty_output(result)

    async def aexecute(
        self,
        command: str,
        *,
        timeout: int | None = None,
    ) -> ExecuteResponse:
        result = await super().aexecute(command, timeout=timeout)
        return self._normalize_empty_output(result)

    @staticmethod
    def _normalize_empty_output(result: ExecuteResponse) -> ExecuteResponse:
        if result.exit_code == 0 and result.output == "<no output>":
            return ExecuteResponse(
                output=EMPTY_OUTPUT_MESSAGE,
                exit_code=result.exit_code,
                truncated=result.truncated,
            )
        return result
