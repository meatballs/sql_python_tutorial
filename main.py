import collections
import logging
import shutil

import click
import daiquiri
import jinja2
from nbconvert import HTMLExporter
from pathlib import Path

daiquiri.setup(level=logging.INFO)
logger = daiquiri.getLogger(__name__)

ENVIRONMENT_ROOTS = {
    'local': '/',
    'gh_pages': '/sql_python_tutorial/'
}

BUILD_FOLDERS = {
    'local': 'build',
    'gh_pages': '.'
}


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


@click.command()
@click.option('--env', type=click.Choice(BUILD_FOLDERS.keys()), default='local')
def main(env):
    logger.info(f'Building site for {env} environment')

    root = ENVIRONMENT_ROOTS[env]
    build_dir = Path(BUILD_FOLDERS[env])
    build_dir.mkdir(exist_ok=True)

    logger.info(f'Output files will be in {build_dir}')

    logger.info('Building Notebooks...')
    nb_dir = Path('notebooks')
    chapter_paths = sorted(nb_dir.glob('./*ipynb'))
    chapters_output_dir = Path(build_dir, 'chapters')
    shutil.rmtree(chapters_output_dir, ignore_errors=True)
    chapters_output_dir.mkdir(exist_ok=True)

    make_collection(
        paths=chapter_paths, directory=chapters_output_dir, root=root)
    logger.info('Done')

    logger.info('Building Chapters...')
    chapters = []
    for path in sorted(chapter_paths):
        chapters.append(Chapter(f"{get_id(path)}",
                                get_name(path), str(path)))

    html = render_template(
        "chapters.html", {"chapters": chapters, "root": root})
    with Path(chapters_output_dir, 'index.html').open('w') as f:
        f.write(html)
    logger.info('Done')

    logger.info('Building Pages...')
    pages_template_dir = Path('templates', 'pages')
    page_templates = pages_template_dir.glob('./*.html')
    pages_output_dir = Path(build_dir, 'pages')
    shutil.rmtree(pages_output_dir, ignore_errors=True)
    pages_output_dir.mkdir(exist_ok=True)

    for template in page_templates:
        if template.stem == 'home':
            output_file = Path(build_dir, 'index.html')
        else:
            output_file = Path(pages_output_dir, template.name)

        html = render_template(
            str(Path('pages', template.name)), {'root': root})
        with output_file.open('w') as f:
            f.write(html)
    logger.info('Done')

    if env == 'local':
        logger.info(f'Copying static files to {build_dir}...')
        static_output_dir = Path(build_dir, 'static')
        shutil.rmtree(static_output_dir)
        shutil.copytree('static', static_output_dir)
        logger.info('Done')

    logger.info('Finished')


if __name__ == '__main__':
    main()
