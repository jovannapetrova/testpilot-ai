import StatusBadge from "../ui/StatusBadge";

export default function ProjectCard({

    project

}){

    return(

        <div className="card project-card">

            <h3>

                {project.name}

            </h3>

            <p>

                {project.language}

            </p>

            <StatusBadge
                status={
                    project.status==="Running"
                    ?"running"
                    :"success"
                }
            />

            <h2>

                {project.quality}/100

            </h2>

        </div>

    );

}