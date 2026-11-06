#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int parent_directory(char *path) {
    char *slash = strrchr(path, '/');
    if (slash == NULL) {
        return 0;
    }
    *slash = '\0';
    return 1;
}

int main(int argc, char **argv) {
    (void)argc;
    (void)argv;

    char executable[PATH_MAX];
    uint32_t executable_size = sizeof(executable);
    if (_NSGetExecutablePath(executable, &executable_size) != 0) {
        return 2;
    }

    char resolved[PATH_MAX];
    if (realpath(executable, resolved) == NULL) {
        return 2;
    }

    char project[PATH_MAX];
    strlcpy(project, resolved, sizeof(project));
    if (!parent_directory(project) || !parent_directory(project) ||
        !parent_directory(project) || !parent_directory(project)) {
        return 2;
    }

    char output_directory[PATH_MAX];
    char log_path[PATH_MAX];
    char script_path[PATH_MAX];
    char python_path[PATH_MAX * 2];
    snprintf(output_directory, sizeof(output_directory), "%s/output", project);
    snprintf(log_path, sizeof(log_path), "%s/launcher.log", output_directory);
    snprintf(script_path, sizeof(script_path), "%s/python_app/app3d.py", project);
    snprintf(
        python_path,
        sizeof(python_path),
        "%s/python_app:%s/.venv/lib/python3.11/site-packages",
        project,
        project
    );

    mkdir(output_directory, 0755);
    freopen(log_path, "a", stdout);
    freopen(log_path, "a", stderr);
    chdir(project);
    setenv("PYTHONPATH", python_path, 1);
    setenv("PYTHONUNBUFFERED", "1", 1);

    wchar_t *program = Py_DecodeLocale(resolved, NULL);
    wchar_t *script = Py_DecodeLocale(script_path, NULL);
    if (program == NULL || script == NULL) {
        return 3;
    }

    Py_SetProgramName(program);
    Py_Initialize();
    wchar_t *python_argv[] = {script};
    PySys_SetArgvEx(1, python_argv, 0);

    FILE *source = fopen(script_path, "r");
    if (source == NULL) {
        fprintf(stderr, "Startdatei fehlt: %s\n", script_path);
        return 4;
    }
    int result = PyRun_SimpleFileExFlags(source, script_path, 1, NULL);
    int finalize_result = Py_FinalizeEx();

    PyMem_RawFree(program);
    PyMem_RawFree(script);
    return result != 0 || finalize_result < 0 ? 1 : 0;
}
