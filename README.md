Nagbot [![Build Status](https://img.shields.io/circleci/build/github/srosenthal/nagbot)](https://circleci.com/gh/srosenthal/nagbot) [![License](https://img.shields.io/github/license/srosenthal/nagbot)](https://github.com/srosenthal/nagbot/blob/master/LICENSE)
=========

# The Problem
Amazon Web Services provides incredible flexibility for quickly spinning up servers with a variety of configurations. The big downside is that it's easy to lose track of AWS resources and end up spending a lot more money than you expected.

At Seeq, we launch a lot of EC2 instances for a variety of development purposes (demos, testing, research & development). But we aren't always good about keeping track of them. Before Nagbot came along, cleaning up unwanted or forgotten EC2 instances was a manual process. I saw an opportunity there and volunteered to implement an automated process.


# Nagbot
Nagbot is a side project I developed at [Seeq](https://seeq.com) and launched in May 2019. It has saved thousands of dollars every month, probably tens of thousands in the few months it has been running so far.

Nagbot does the following:
1. Query for all EC2 Instances, Volumes, AMIs, and Snapshots in an account, along 
   with important metadata (Name, OS, Monthly Price, size, etc.)
2. Post this information to a Slack channel and also dump the table into a Google Sheet for analysis and auditing
3. Look at the "Stop after" tag, which is by convention a YYYY-MM-DD date, and after a warning period, stop any 
   unwanted resources.
4. Look at the "Terminate after" tag, which is by convention a YYYY-MM-DD date, and terminate any unwanted resources.

Here's what a Nagbot notification looks like in Slack:
![Example of Nagbot's Slack message](https://github.com/srosenthal/nagbot/blob/master/nagbot-slack.png "Example of Nagbot's Slack message")

# Setting up Slack for Nagbot

Here is a [recording of the process to setup a Slack app](https://seeq.zoom.us/rec/share/qgmqAvz_2eV3SYiNJO4mLrQlH94eGXSs89BDSl28Epl-Bjey9_DgvBLnkF3W2dOf.Zd12Sq-G5QbsOPrt) (Passcode: z?mJ%d08). The process frequently changes due to Slack changing the UI for applications.

# Testing Nagbot changes during development

The NagBotTest app has been registered to slack, and it is set up to send NagBot output to slack. The default 
testing channel for NagBot is #bot-testing. 

For Seeq employees looking to test changes to NagBot during development, the SLACK_BOT_TOKEN for NagBotTest is found on 
Keeper [here]
(https://keepersecurity.
com/vault/#detail/AUj3FYXz44uON4CVQSTKMQ).

# Releasing New Versions (Seeq Employees)

Update the version at the top of nagbot.py to vX.Y.Z, commit, and push your changes

Tag the version in git:

```sh
git fetch && git switch --detach origin/master
git tag vX.Y.Z
git push --tags
```

Wait for GitHub Actions to publish the new tag to [JFrog](https://seeq.jfrog.io/ui/packages/docker:%2F%2Fnagbot)

For access to JFrog, see the [JFrog Confluence Page](https://seeq.atlassian.net/wiki/spaces/SQ/pages/2266562701/JFrog)

Promote to `prod` using:

```sh
jfrog rt docker-promote nagbot nagbot-docker-dev-local nagbot-docker-prod-local --copy=true --source-tag=vX.Y.Z
```

Next, apply the newly created 'prod' image's tag to the NagBot Job in the build infra cluster. To do this, check out 
the [devops](https://github.com/seeq12/devops) repo, create a new branch, then update the docker tag in
`devops/devops/build-infra-cluster/nagbot/jobs.yaml`. After connecting to the build infra cluster by following 
instructions [How to Access the Build Infra Cluster](https://seeq.atlassian.net/wiki/spaces/SQ/pages/2317386552/How+to+Access+the+Dev-Infra+Cluster), apply the updated version to the cluster using: 
```sh
kubectl apply -f devops/devops/build-infra-cluster/nagbot/jobs.yaml
```
Finally, create a PR with the updated jfrog version in the devops repo.
