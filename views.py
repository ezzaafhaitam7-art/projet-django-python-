from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import logout 

from base.models import Bien
from .models import Locataire, Contrat, Paiement, Demande
from .models import Client
from datetime import date, timedelta


def liste_biens(request):
    biens = Bien.objects.all()
    return render(request, 'base/biens.html', {'biens': biens})

def bien_detail(request, pk):
    bien = get_object_or_404(Bien, pk=pk)
    return render(request, 'base/bien_detail.html', {'bien': bien})

def louer_bien(request, bien_id):
    bien = get_object_or_404(Bien, id=bien_id)
    
    if request.method == 'POST':
        message = request.POST.get('message')
        
        # 1. RÉCUPÉRER LE PROFIL CLIENT
        # On cherche le 'Client' qui appartient à l'utilisateur connecté (request.user)
        try:
            profil_client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            # Si l'utilisateur n'a pas de profil (ex: admin qui n'est pas passé par l'inscription)
            return render(request, 'base/erreur.html', {
                'message': "Erreur : Votre profil client n'existe pas. Veuillez vous inscrire via le formulaire."
            })

        # 2. CRÉER LA DEMANDE
        # C'est ici qu'on règle l'erreur : on donne le 'profil_client' à la colonne 'client'
        Demande.objects.create(
            client=profil_client,  # On remplit la colonne qui était vide (NULL)
            bien=bien,
            message=message,
            statut='En attente'
        )
        
        return redirect('mes_demandes')

    return render(request, 'base/louer_form.html', {'bien': bien})
# --- SYSTÈME DE CONNEXION ---

def login_personnalise(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            # FORCE LA REDIRECTION VERS L'ACCUEIL ICI
            return redirect('/') 
        else:
            messages.error(request, "Identifiants invalides")
    return render(request, 'base/login.html')
# --- VUES PROTÉGÉES (Redirigent vers ton login personnalisé) ---

@login_required(login_url='/biens/login/')
def liste_locataires(request):
    locataires = Locataire.objects.all()
    return render(request, 'base/locataires.html', {'locataires': locataires})

@login_required(login_url='/biens/login/')
def liste_contrats(request):
    contrats = Contrat.objects.all()
    return render(request, 'base/contrats.html', {'contrats': contrats})

@login_required(login_url='/biens/login/')
def liste_paiements(request):
    paiements = Paiement.objects.all()
    return render(request, 'base/paiements.html', {'paiements': paiements})



def inscription(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # On récupère les valeurs via les attributs 'name' du HTML
            Client.objects.create(
                user=user,
                nom_complet=request.POST.get('nom_complet'),
                cin=request.POST.get('cin'),
                telephone=request.POST.get('telephone'),
                adresse=request.POST.get('adresse'),
                profession=request.POST.get('profession'),
                date_naissance=request.POST.get('date_naissance')
            )
            return render(request, 'base/inscription_succes.html')
    else:
        form = UserCreationForm()
    return render(request, 'base/inscription.html', {'form': form})

@login_required(login_url='mon_login')
def mes_demandes(request):
    # 1. On récupère le profil Client correspondant à l'utilisateur connecté (ex: adam)
    try:
        profil_client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        # Si l'utilisateur n'a pas encore créé son profil Client
        return render(request, 'base/erreur.html', {
            'message': "Profil client introuvable. Veuillez compléter votre inscription."
        })

    # 2. On filtre les demandes en utilisant l'objet 'profil_client' 
    # (et non pas request.user)
    demandes = Demande.objects.filter(client=profil_client)

    return render(request, 'base/mes_demandes.html', {'demandes': demandes})

def deconnexion_manuelle(request):
    logout(request)
    # On vide les messages pour éviter les bugs au rafraîchissement
    storage = messages.get_messages(request)
    storage.used = True
    return redirect('/')


# 1. Vue pour afficher TOUTES les demandes à l'administrateur
@login_required(login_url='mon_login')
def gestion_demandes(request):
    # TEMPORAIREMENT DÉSACTIVÉ POUR TESTER
    # if not request.user.is_staff:
    #     return redirect('/')
    
    demandes = Demande.objects.all().order_by('-date_demande')
    return render(request, 'base/gestion_demandes.html', {'demandes': demandes})

# 2. Vue pour ACCEPTER une demande et transformer le Client en Locataire
from datetime import date, timedelta  # Assure-toi d'avoir ces imports en haut du fichier

@login_required(login_url='mon_login')
# ... (tes imports restent identiques) ...

@login_required(login_url='mon_login')
def accepter_demande(request, pk):
    # Si tu utilises une interface admin personnalisée, on laisse tout utilisateur connecté traiter les demandes.
    # if not request.user.is_staff:
    #     return redirect('/')

    demande = get_object_or_404(Demande, pk=pk)
    client = demande.client
    bien = demande.bien

    try:
        # 1. Créer le Locataire d'abord
        # On utilise l'email pour vérifier s'il existe déjà
        locataire, created = Locataire.objects.get_or_create(
            email=client.user.email,
            defaults={
                'nom': client.nom_complet,
                'prenom': client.cin,
                'telephone': client.telephone
            }
        )

        # 2. Créer le Contrat
        nouveau_contrat = Contrat.objects.create(
            bien=bien,
            locataire=locataire,
            date_debut=date.today(),
            date_fin=date.today() + timedelta(days=365)
        )

        # 3. Créer le Paiement (On convertit le prix en nombre pur)
        # On utilise float() seulement si bien.Prix est une chaîne, sinon direct
        montant_final = float(str(bien.Prix).replace(',', '.')) 
        
        Paiement.objects.create(
            contrat=nouveau_contrat,
            montant=montant_final,
            date_paiement=date.today(),
            statut='Payé'
        )

        # 4. Mettre à jour les statuts à la FIN
        demande.statut = 'Acceptée'
        demande.save()
        
        bien.Statut = 'Loué'
        bien.save()

        messages.success(request, f"Succès ! {client.nom_complet} est maintenant locataire et le contrat est généré.")

    except Exception as e:
        # Si ça rate, on affiche l'erreur exacte
        messages.error(request, f"Erreur lors de la création : {str(e)}")
        print(f"DEBUG ERREUR: {e}")

    return redirect('gestion_demandes')

@login_required(login_url='mon_login')
def refuser_demande(request, pk):
    # Sécurité : Seul Haitam peut refuser
    if not request.user.is_staff:
        return redirect('/')
        
    demande = get_object_or_404(Demande, pk=pk)
    
    # On change simplement le statut sans créer de locataire ou contrat
    demande.statut = 'Refusée'
    demande.save()
    
    messages.warning(request, f"La demande de {demande.client.nom_complet} a été refusée.")
    return redirect('gestion_demandes')