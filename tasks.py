import collections
import logging
import shutil
import http.server
import os

import daiquiri
import jinja2
from invoke import task, call
from nbconvert import HTMLExporter
from pathlib import Path

daiquiri.setup(level=logging.INFO)
logger = daiquiri.getLogger(__name__)

ROOTS = {
    'local': '/',
    'gh_pages': '/sql_python_tutorial/'
}

BUILD_DIRS = {
    'local': 'build',
    'gh_pages': '.'
}


def static_dir(env):
    if env == 'local':
        return Path(BUILD_DIRS[env], 'static')
    else:
        return None


def get_id(path):
    """The numeric id of the file name as a string

    e.g. The id of a file named '01-Test-File' would be '01'
    """
    stem = path.stem
    try:
        return stem[:stem.index('-')]
    except ValueError:
        stem = stem.lower()
        stem = stem.replace(" ", "-")
        stem = stem.replace(",", "")
        return stem


def get_name(path):
    """The file name stripped of any numeric id


    e.g. the name of a file '01-Test-File' would be 'Test-File'
    """
    stem = path.stem
    try:
        return stem[stem.index('-'):].replace('-', ' ')
    except ValueError:
        return stem


def convert_html(nb_path):
    """
    Convert a notebook to html
    """
    html_exporter = HTMLExporter()
    html_exporter.template_file = "basic"
    return html_exporter.from_file(str(nb_path))


def render_template(template_file, template_vars):
    """
    Render a jinja2 template
    """
    templateLoader = jinja2.FileSystemLoader(searchpath="./templates/")
    template_env = jinja2.Environment(loader=templateLoader)
    template = template_env.get_template(template_file)
    return template.render(template_vars)


def make_dir(path, directory, root, previous_url=None, next_url=None):
    """
    Create a directory for the name of the file
    """
    path_id = get_id(path)
    p = Path(directory, path_id)
    p.mkdir(exist_ok=True)
    nb, _ = convert_html(path)
    nb = nb.replace("{{root}}", root)
    html = render_template("notebook.html", {
        "nb": nb,
        "root": root,
        "id": path_id,
        "previous_url": previous_url,
        "next_url": next_url})
    with Path(p, 'index.html').open('w') as f:
        f.write(html)


def make_collection(paths, directory, root,
                    make_previous_url=True,
                    make_next_url=True):

    number_of_paths = len(paths)
    for index, filename in enumerate(paths):
        previous_id = None
        if index > 0:
            previous_path = paths[(index - 1) % number_of_paths]
            previous_id = get_id(previous_path)

        next_id = None
        if index + 1 < number_of_paths:
            next_path = paths[(index + 1) % number_of_paths]
            next_id = get_id(next_path)

        make_dir(
            Path(filename),
            directory=directory,
            root=root,
            previous_url=previous_id,
            next_url=next_id)


Chapter = collections.namedtuple("chapter", ["dir", "title", "nb"])


def setup_base_context(c):
    c.notebook_dir = Path('notebooks')
    c.chapter_paths = sorted(c.notebook_dir.glob('./*ipynb'))
    pages_template_dir = Path('templates', 'pages')
    c.page_templates = list(pages_template_dir.glob('./*.html'))


def setup_env_context(c, env):
    setup_base_context(c)
    c.env = env
    c.chapters_output_dir = Path(BUILD_DIRS[c.env], 'chapters')
    c.pages_output_dir = Path(BUILD_DIRS[c.env], 'pages')
    c.static_dir = static_dir(env)


@task
def update_notebooks(c):
    with c.cd(str(c.notebook_dir)):
        status = c.run('git diff-index --quiet HEAD')
    if status.exited:
        logger.info('Updating notebooks submodule...')
        with c.cd(str(c.notebook_dir)):
            c.run('git pull')
        c.run('git add -A')
        c.run('git commit -m "Update notebooks"')
        logger.info('Done')
    else:
        logger.info('Notebooks submodule up to date')


@task
def build_notebooks(c):
    logger.info('Building Notebooks...')
    shutil.rmtree(c.chapters_output_dir, ignore_errors=True)
    c.chapters_output_dir.mkdir(exist_ok=True)

    make_collection(
        paths=c.chapter_paths, directory=c.chapters_output_dir,
        root=ROOTS[c.env])
    logger.info('Done')


@task
def build_contents_page(c):
    logger.info('Building Contents...')
    chapters = []
    for path in sorted(c.chapter_paths):
        chapters.append(Chapter(f"{get_id(path)}",
                                get_name(path), str(path)))

    html = render_template(
        'chapters.html', {'chapters': chapters, "root": ROOTS[c.env]})
    with Path(c.chapters_output_dir, 'index.html').open('w') as f:
        f.write(html)
    logger.info('Done')


@task
def build_pages(c):
    logger.info('Building Pages...')

    shutil.rmtree(c.pages_output_dir, ignore_errors=True)
    c.pages_output_dir.mkdir(exist_ok=True)

    for template in c.page_templates:
        if template.stem == 'home':
            output_file = Path(BUILD_DIRS[c.env], 'index.html')
        else:
            output_file = Path(c.pages_output_dir, template.name)

        html = render_template(
            str(Path('pages', template.name)), {'root': ROOTS[c.env]})
        with output_file.open('w') as f:
            f.write(html)
    logger.info('Done')


@task
def copy_static_files(c):
    if c.static_dir is not None:
        logger.info(f'Copying static files to {c.static_dir}...')
        shutil.rmtree(c.static_dir, ignore_errors=True)
        shutil.copytree('static', c.static_dir)
        logger.info('Done')


@task(post=[
    update_notebooks, build_notebooks, build_contents_page, build_pages,
    copy_static_files])
def build(c, env='local'):
    setup_env_context(c, env)


@task
def serve(c, env='local'):
    handler_class = http.server.SimpleHTTPRequestHandler
    os.chdir(BUILD_DIRS[env])
    http.server.test(HandlerClass=handler_class, port=8000)


@task
def push_changes(c):
    status = c.run('git status --porcelain')
    if status.stdout:
        logger.info('Site Rebuilt. Publishing changes...')
        c.run('git add -A')
        c.run('git commit -m "Rebuild site"')
        c.run('git push')
        logger.info('Done')
    else:
        logger.info('No changes to publish')


@task(post=[
    update_notebooks, build_notebooks, build_contents_page, build_pages,
    copy_static_files, push_changes])
def publish(c):
    setup_env_context(c, 'gh_pages')
