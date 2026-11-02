Scenario storyboard
===================

The `ws4 storyboard` command writes a one-page Markdown narrative from an
existing run's `account_values.csv`:

.. code-block:: bash

   ws4 storyboard --run runtime/my-run --out runtime/my-run/storyboard.md

It uses the account-derived forest-condition card from P91 and adds the
storyboard framing and limits. Derived indicators remain `review_required`;
alerts are advisory and no objective, constraint, growth, schedule, or solver
setting is changed. This is a shareable reporting view, not an operational
plan.
