import boto3
from os import mkdir
from os import getcwd
from os import remove
from shutil import copy2
from shutil import rmtree
from shutil import make_archive
from utils import Utils
from zipfile import ZipFile
from urllib import urlretrieve


class Project:

    def __init__(self, conf, projectname):
        self.conf = conf
        if projectname != "":
            self.projectname = projectname
        else:
            print("Parameter --projectname is required.")
            exit(1)

    def create_project(self):
        Utils.validate_reserved_sections(self.conf, self.projectname)
        if self.conf.config.has_section(self.projectname):
            print("Project '" + self.projectname + "' already exists.")
            exit(1)
        else:
            self.conf.config.add_section(self.projectname)
            mkdir(self.conf.vars['C_LAMBDAS_DIR'] + self.projectname)
            open(self.conf.vars['C_LAMBDAS_DIR'] + self.projectname + "/__init__.py", 'a').close()
            copy2(self.conf.vars['C_LAMBDASTANDARD_FUNC'], self.conf.vars['C_LAMBDAS_DIR']
                  + self.projectname + "/index.py")
            print("Project " + self.projectname + " has been created.")
            self.conf.config.set(self.projectname, "deployed", "False")

        return self.conf


    def import_project(self):
        if self.conf.config.has_section(self.projectname):
            print("Project " + self.projectname + " already exists in your configuration.")
            exit(1)

        lbs = boto3.client('lambda')

        try:
            lambda_function = lbs.get_function(FunctionName=self.projectname)
            zippath = (getcwd() + "/" + self.conf.vars['C_LAMBDAS_DIR'] +
                       self.conf.vars['C_LAMBDAS_ZIP_DIR'] + self.projectname + ".zip")
            destfolder = getcwd() + "/" + self.conf.vars['C_LAMBDAS_DIR'] + self.projectname
            urlretrieve(lambda_function['Code']['Location'], zippath)
            zip_ref = ZipFile(zippath, 'r')
            mkdir(destfolder)
            open(self.conf.vars['C_LAMBDAS_DIR'] + self.projectname + "/__init__.py", 'a').close()
            zip_ref.extractall(destfolder)
            zip_ref.close()
            self.conf.config.add_section(self.projectname)
            self.conf.config.set(self.projectname, "deployed", "True")
            print("Project " + self.projectname + " imported.")
        except Exception as e:
            print(str(e))
            print("The project " + self.projectname + " does not exist in AWS environment.")
            exit(1)

        return self.conf

    def deploy_project(self, rolename):
        rolename = Utils.define_lambda_role(self.conf, rolename)

        if not self.conf.config.has_section(self.projectname):
            print("Project " + self.projectname + " does not exist.")
            exit(1)

        lbs = boto3.client('lambda')
        lambdafolder = getcwd() + "/" + self.conf.vars['C_LAMBDAS_DIR'] + "/" + self.projectname
        zipfolder = (getcwd() + "/" + self.conf.vars['C_LAMBDAS_DIR'] +
                     self.conf.vars['C_LAMBDAS_ZIP_DIR'] + self.projectname)
        make_archive(zipfolder, "zip", lambdafolder)

        try:
            lbs.get_function(FunctionName=self.projectname)
            replace = True
        except Exception:
            replace = False

        try:
            if replace:
                lbs.update_function_code(
                    FunctionName=self.projectname,
                    ZipFile=open(self.conf.vars['C_LAMBDAS_DIR'] + self.conf.vars[
                        'C_LAMBDAS_ZIP_DIR'] + self.projectname + ".zip", "rb").read()
                )
                print("Lambda project " + self.projectname + " was redeployed.")
            else:
                lbs.create_function(
                    FunctionName=self.projectname,
                    Runtime='python2.7',
                    Role=rolename,
                    Handler='index.lambda_handler',
                    Description="Lambda project " + self.projectname + " deployed by lambda-proxy",
                    Code={
                        'ZipFile': open(self.conf.vars['C_LAMBDAS_DIR'] + self.conf.vars[
                            'C_LAMBDAS_ZIP_DIR'] + self.projectname + ".zip", "rb").read()
                    }
                )
                print("Lambda project " + self.projectname + " was created and deployed.")

            self.conf.config.set(self.projectname, "deployed", "True")

        except Exception as e:
            print("Failed to create the lambda project.")
            print(str(e))

        remove(zipfolder+".zip")
        return self.conf

    def delete_project(self):
        Utils.validate_reserved_sections(self.conf, self.projectname)
        if self.conf.config.has_section(self.projectname):
            self.conf = self.undeploy_project()
            self.conf.config.remove_section(self.projectname)
            rmtree(self.conf.vars['C_LAMBDAS_DIR'] + self.projectname)
            print("Project '" + self.projectname + "' has been deleted.")
        else:
            print("Project '" + self.projectname + "' does not exist.")
            exit(1)

        return self.conf

    def undeploy_project(self):
        if not self.conf.config.has_section(self.projectname):
            print("Project '" + self.projectname + "' does not exist.")
            exit(1)

        lbs = boto3.client('lambda')
        try:
            lbs.delete_function(FunctionName=self.projectname)
            print("Project '" + self.projectname + "' is now undeployed.")
        except Exception as e:
            print("Project '" + self.projectname + "' is not deployed.")

        self.conf.config.set(self.projectname, "deployed", "False")

        return self.conf
