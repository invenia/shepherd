.. _actions:

Actions
============

Actions describe operations to run on stacks and environments. Several sample actions are provided in ``shepherd/actions``, however, you can define your own by simply subclassing ``Action`` and providing a ``run`` method. Actions are also composible by running and sub action inside your ``run`` method. Currently, the only reason Actions are objects rather than just functions is so that they can be Yapsy plugins. This may change in future release if we choose to move away from Yapsy.

Sample Ansible Action:

.. literalinclude:: ../../shepherd/actions/ansible.py


Which can be run with by calling ``run`` with the name of the action, a config object and group of named parameters to pass to the Action

In the case of the Ansible Action this would look like::

    run(
        'Ansible',
        config,
        name={global_stack_name},
        path={playbook_dir_path},
        playbook={playbook_name},
        vault_key_file={path_to_vault_key_file),
    )
