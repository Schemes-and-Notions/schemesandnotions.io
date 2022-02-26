#!/usr/bin/env python

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EC2
#from diagrams.k8s
from diagrams.onprem import network, vcs, ci
from diagrams.custom import Custom
from matplotlib.pyplot import margins


graph_attr = {
    "fontsize": "35",
    #"margin": "3x3",
#    "bgcolor": "green"
}

with Diagram(show=False, filename="topology", outformat="png", graph_attr=graph_attr):
    
    with Cluster("K8s cluster"):
        proxy = network.Traefik("Traefik Ingress")
        gitea = vcs.Gitea("Gitea\ngitea.zeroent.lab")
        drone = ci.Droneci("DroneCI Server\ndrone.zeroent.lab")
        k8sCluster = [ 
        proxy >> Edge() << gitea,
        proxy >> Edge() << drone
        ]

    with Cluster("Docker host",direction="BT"):
        runner = ci.DroneCI("DroneCI 'Agent'")
        drunner = ci.DroneCI("DroneCI Runner")
        #runner >> Edge() << drunner
        runner >> Edge() << proxy
        drunner >> Edge() << proxy
    
    smallstep = Custom(label="SmallStep CA",icon_path="./smallstep-icon.png")
    smallstep >> Edge(label="ACME") << proxy
    