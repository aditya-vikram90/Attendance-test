pipeline {
    agent any

    environment {
        REGISTRY_HOST = 'ghcr.io'
        GITHUB_USER   = 'aditya-vikram90'
        IMAGE_NAME    = 'ghcr.io/aditya-vikram90/attendance-service'
        IMAGE_TAG     = "${env.BUILD_NUMBER}"
        DEPLOY_PATH   = '/opt/attendance-stack'
    }

    options {
        timeout(time: 15, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Python Lint') {
            steps {
                sh '''
                    CID=$(hostname 2>/dev/null || echo "jenkins")
                    docker run --rm --volumes-from "$CID" -w "$PWD/attendance-service" python:3.12-slim bash -c "
                        pip install --no-cache-dir flake8 && \
                        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
                    "
                '''
            }
        }

        stage('Compile Keycloak Java SPI') {
            steps {
                sh '''
                    CID=$(hostname 2>/dev/null || echo "jenkins")
                    docker run --rm --volumes-from "$CID" -w "$PWD/keycloak-spi" maven:3.9-eclipse-temurin-21 mvn clean package -DskipTests
                    ls -lh keycloak-spi/target/*.jar
                '''
            }
        }

        stage('Build & Tag Docker Image') {
            steps {
                sh """
                    cd attendance-service
                    docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -t ${IMAGE_NAME}:latest .
                """
            }
        }

        stage('Push to GitHub Container Registry') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'ghcr-credentials', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')]) {
                    sh """
                        echo "\$GH_TOKEN" | docker login "${REGISTRY_HOST}" -u "\$GH_USER" --password-stdin
                        docker push "${IMAGE_NAME}:${IMAGE_TAG}"
                        docker push "${IMAGE_NAME}:latest"
                        docker logout "${REGISTRY_HOST}"
                    """
                }
            }
        }

        stage('Deploy to AWS Server') {
            steps {
                withCredentials([
                    string(credentialsId: 'aws-server-ip', variable: 'SERVER_IP'),
                    usernamePassword(credentialsId: 'ghcr-credentials', usernameVariable: 'GH_USER', passwordVariable: 'GH_TOKEN')
                ]) {
                    sshagent(['aws-ec2-ssh-key']) {
                        sh """
                            # 1. Transfer SPI JAR
                            scp -o StrictHostKeyChecking=no keycloak-spi/target/keycloak-attendance-user-storage-1.0.0.jar \
                                ubuntu@\${SERVER_IP}:\${DEPLOY_PATH}/local-replica/providers/

                            # 2. Deploy container on AWS
                            ssh -o StrictHostKeyChecking=no ubuntu@\${SERVER_IP} "bash -s" << EOF
                                cd \${DEPLOY_PATH}
                                echo "\${GH_TOKEN}" | docker login "\${REGISTRY_HOST}" -u "\${GH_USER}" --password-stdin
                                docker pull "\${IMAGE_NAME}:latest"
                                docker tag "\${IMAGE_NAME}:latest" localhost/attendance:latest
                                docker compose up -d --no-deps attendance
                                docker restart keycloak
                                sleep 5
                                HEALTH=\\\$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8090/healthz || echo "000")
                                echo "Health check HTTP status: \\\$HEALTH"
                                [ "\\\$HEALTH" -eq 200 ] || [ "\\\$HEALTH" -eq 302 ] || exit 1
EOF
                        """
                    }
                }
            }
        }
    }

    post {
        success {
            echo "✓ Deployment successful! Image ${IMAGE_NAME}:${IMAGE_TAG} is live."
        }
        failure {
            echo "✗ Deployment failed! Check the console output."
        }
    }
}
