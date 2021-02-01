import os, shutil

path = os.path.abspath('./shared_resources')
if os.path.isdir(path):
    for item_name in os.listdir(path):
        print(f'Copying shared resource: {item_name}')
        item = os.path.join(path, item_name)
        if os.path.isfile(item):
            shutil.copyfile(item, './'+item_name)
            shutil.copyfile(item, './EmailBlockerLite/'+item_name)
        else:
            try:
                shutil.copytree(item, './'+item_name)
            except FileExistsError:
                shutil.rmtree('./'+item_name)
            finally:
                shutil.copytree(item, './'+item_name)
            try:
                shutil.copytree(item, './EmailBlockerLite/'+item_name)
            except FileExistsError:
                shutil.rmtree('./EmailBlockerLite/'+item_name)
            finally:
                shutil.copytree(item, './EmailBlockerLite/'+item_name)
    print('Removing shared resource dir')
    shutil.rmtree('./shared_resources')